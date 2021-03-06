from __future__ import print_function
import trident
import numpy as np
import yt
import os
import MISTY
import sys
import os
import argparse

from astropy.table import Table

from get_refine_box import get_refine_box
from get_proper_box_size import get_proper_box_size
from get_halo_center import get_halo_center

import show_velphase as sv

import getpass

from math import pi

def parse_args():
    '''
    Parse command line arguments.  Returns args object.
    '''
    parser = argparse.ArgumentParser(description="extracts spectra from refined region")

    parser.add_argument('--velocities', dest='velocities', action='store_true',
                            help='make the velocity plots?, default is no')
    parser.set_defaults(velocities=False)

    parser.add_argument('--run', metavar='run', type=str, action='store',
                        help='which run? default is natural')
    parser.set_defaults(run="natural")

    parser.add_argument('--output', metavar='output', type=str, action='store',
                        help='which output? default is RD0020')
    parser.set_defaults(output="RD0020")

    parser.add_argument('--system', metavar='system', type=str, action='store',
                        help='which system are you on? default is oak')
    parser.set_defaults(system="oak")

    parser.add_argument('--Nrays', metavar='Nrays', type=int, action='store',
                        help='how many sightlines do you want? default is 1')
    parser.set_defaults(Nrays="1")

    args = parser.parse_args()
    return args


def get_refined_ray_endpoints(ds, halo_center, track, **kwargs):
    '''
    returns ray_start and ray_end for a ray with a given
    impact parameter along a given axis, only within the refined box
    '''
    impact = kwargs.get("impact", 25.)
    angle = kwargs.get("angle", 2*pi*np.random.uniform())
    refine_box, refine_box_center, x_width = get_refine_box(ds, ds.current_redshift, track)
    proper_box_size = get_proper_box_size(ds)

    ray_start = np.zeros(3)
    ray_end = np.zeros(3)
    #### for now, ray has random y (sets impact), goes from -z to +z, in y direction, x is random
    ray_start[0] = np.float(refine_box.left_edge[0].value)
    ray_end[0] = np.float(refine_box.right_edge[0].value)
    ray_start[1] = halo_center[1] + (impact/proper_box_size) * np.cos(angle)
    ray_end[1] = halo_center[1] + (impact/proper_box_size) * np.cos(angle)
    ray_start[2] = halo_center[2] + (impact/proper_box_size) * np.sin(angle)
    ray_end[2] = halo_center[2] + (impact/proper_box_size) * np.sin(angle)

    return np.array(ray_start), np.array(ray_end)

def quick_spectrum(ds, triray, filename, **kwargs):

    line_list = kwargs.get("line_list", ['H I 1216', 'Si II 1260', 'Mg II 2796', 'C III 977', 'C IV 1548', 'O VI 1032'])
    redshift = ds.get_parameter('CosmologyCurrentRedshift')

    ldb = trident.LineDatabase('atom_wave_gamma_f.dat')
    sg = trident.SpectrumGenerator(lambda_min=1000.,
                                       lambda_max=4000.,
                                       dlambda=0.01,
                                       line_database='atom_wave_gamma_f.dat')

    sg.make_spectrum(triray, line_list, min_tau=1.e-5,store_observables=True)

    restwave = sg.lambda_field / (1. + redshift)
    out_spectrum = Table([sg.lambda_field, restwave, sg.flux_field])
    out_spectrum.write(filename+'.fits')

def generate_random_rays(ds, halo_center, **kwargs):
    '''
    generate some random rays
    '''
    low_impact = kwargs.get("low_impact", 10.)
    high_impact = kwargs.get("high_impact", 45.)
    track = kwargs.get("track","halo_track")
    Nrays = kwargs.get("Nrays",50)
    output_dir = kwargs.get("output_dir",".")
    haloname = kwargs.get("haloname","somehalo")
    # line_list = kwargs.get("line_list", ['H I 1216', 'Si II 1260', 'C II 1334', 'Mg II 2796', 'C III 977', 'Si III 1207', 'C IV 1548', 'O VI 1032'])
    line_list = kwargs.get("line_list", ['H I 1216', 'H I 1026', 'H I 973', 'H I 950', 'H I 919', \
                     'Si II 1260', 'Si III 1207', 'Si IV 1394', \
                     'C II 1335', 'C III 977', 'C IV 1548', \
                     'O VI 1032'])
    # line_list = kwargs.get("line_list", ['H I 1216', 'Si III 1207','O VI 1032'])

    proper_box_size = get_proper_box_size(ds)
    refine_box, refine_box_center, x_width = get_refine_box(ds, zsnap, track)
    proper_x_width = x_width*proper_box_size

    ## for now, assume all are z-axis
    axis = "x"
    np.random.seed(17)
    impacts = np.random.uniform(low=low_impact, high=high_impact, size=Nrays)
    angles = np.random.uniform(low=0, high=2*pi, size=Nrays)
    out_ray_basename = ds.basename + "_ray_" + axis

    for i in range(Nrays):
        os.chdir(output_dir)
        this_out_ray_basename = out_ray_basename + "_i"+"{:05.1f}".format(impacts[i]) + \
                        "-a"+"{:4.2f}".format(angles[i])
        out_ray_name =  this_out_ray_basename + ".h5"
        rs, re = get_refined_ray_endpoints(ds, halo_center, track, impact=impacts[i])
        out_fits_name = "hlsp_misty_foggie_"+haloname+"_"+ds.basename.lower()+"_i"+"{:05.1f}".format(impacts[i]) + \
                        "-a"+"{:4.2f}".format(angles[i])+"_v3_los.fits"
        rs = ds.arr(rs, "code_length")
        re = ds.arr(re, "code_length")
        if args.velocities:
            trident.add_ion_fields(ds, ions=['Si II', 'Si III', 'Si IV', 'C II', 'C III', 'C IV', 'O VI', 'Mg II'])
        ray = ds.ray(rs, re)
        ray.save_as_dataset(out_ray_name, fields=["density","temperature", "metallicity"])

        if args.velocities:
            ray_df =  ray.to_dataframe(["x","y","z","density","temperature","metallicity","HI_Density",
                                    "x-velocity", "y-velocity", "z-velocity",
                                    "C_p2_number_density", "C_p3_number_density", "H_p0_number_density",
                                    "Mg_p1_number_density", "O_p5_number_density","Si_p2_number_density"])

        out_tri_name = this_out_ray_basename + "_tri.h5"
        triray = trident.make_simple_ray(ds, start_position=rs.copy(),
                                  end_position=re.copy(),
                                  data_filename=out_tri_name,
                                  lines=line_list,
                                  ftype='gas')

        ray_start = triray.light_ray_solution[0]['start']
        ray_end = triray.light_ray_solution[0]['end']
        print("final start, end = ", ray_start, ray_end)
        filespecout_base = this_out_ray_basename + '_spec'
        print(ray_start, ray_end, filespecout_base)

        hdulist = MISTY.write_header(triray,start_pos=ray_start,end_pos=ray_end,
                      lines=line_list, impact=impacts[i])
        tmp = MISTY.write_parameter_file(ds,hdulist=hdulist)

        # quick_spectrum(ds, triray, filespecout_base)

        for line in line_list:
            sg = MISTY.generate_line(triray, line,
                                     zsnap=ds.current_redshift,
                                     write=True,
                                     hdulist=hdulist,
                                     use_spectacle=True)
            filespecout = filespecout_base+'_'+line.replace(" ", "_")+'.png'
            ## if we write our own plotting routine, we can overplot the spectacle fits
            sg.plot_spectrum(filespecout,flux_limits=(0.0,1.0))
            if args.velocities and ('H' in line):
                sv.show_velphase(ds, ray_df, rs, re, triray, filespecout_base)

        MISTY.write_out(hdulist,filename=out_fits_name)



if __name__ == "__main__":

    args = parse_args()
    if args.system == "oak":
        ds_base = "/astro/simulations/FOGGIE/"
        output_path = "/Users/molly/Dropbox/foggie-collab/"
    elif args.system == "dhumuha" or args.system == "palmetto":
        ds_base = "/Users/molly/foggie/"
        output_path = "/Users/molly/Dropbox/foggie-collab/"
    elif args.system == "nmearl":
        ds_base = "/astro/simulations/FOGGIE/"
        output_path = "/Users/nearl/Desktop/"

    if args.run == "natural":
        ds_loc = ds_base + "halo_008508/nref11n/natural/" + args.output + "/" + args.output
        track_name = ds_base + "halo_008508/nref11n/nref11n_nref10f_refine200kpc/halo_track"
        output_dir = output_path + "plots_halo_008508/nref11n/natural/spectra/"
        haloname = "halo008508_nref11n"
    elif args.run == "nref10f":
        ds_loc =  ds_base + "halo_008508/nref11n/nref11n_nref10f_refine200kpc/" + args.output + "/" + args.output
        track_name = ds_base + "halo_008508/nref11n/nref11n_nref10f_refine200kpc/halo_track"
        output_dir = output_path + "plots_halo_008508/nref11n/nref11n_nref10f_refine200kpc/spectra/"
        haloname = "halo008508_nref11n_nref10f"
    elif args.run == "nref11f":
        ds_loc =  ds_base + "halo_008508/nref11n/nref11f_refine200kpc/" + args.output + "/" + args.output
        track_name = ds_base + "halo_008508/nref11n/nref11f_refine200kpc/halo_track"
        output_dir = output_path + "plots_halo_008508/nref11n/nref11f_refine200kpc/spectra/"
        haloname = "halo008508_nref11f"

    ds = yt.load(ds_loc)

    print("opening track: " + track_name)
    track = Table.read(track_name, format='ascii')
    track.sort('col1')
    zsnap = ds.get_parameter('CosmologyCurrentRedshift')
    refine_box, refine_box_center, x_width = get_refine_box(ds, zsnap, track)
    halo_center = get_halo_center(ds, refine_box_center)[0]

    generate_random_rays(ds, halo_center, haloname=haloname, track=track, \
                         output_dir=output_dir, Nrays=args.Nrays)

    # generate_random_rays(ds, halo_center, line_list=["H I 1216"], haloname="halo008508", Nrays=100)
    sys.exit("~~~*~*~*~*~*~all done!!!! spectra are fun!")
