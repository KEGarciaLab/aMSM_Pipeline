#!/usr/bin/env python3.11

import argparse
import sys
from os import listdir, path, makedirs, remove, walk
from re import compile, sub
from subprocess import check_output, run
from time import sleep
from string import Template
from typing import Literal
from shutil import copy2
from datetime import datetime
from math import sqrt
from fnmatch import fnmatch



# class for logging
class Tee:
    def __init__(self, real_stream, *other_streams):
        self.real_stream = real_stream
        self.other_streams = other_streams

    def write(self, message):
        self.real_stream.write(message)
        self.real_stream.flush()
        for stream in self.other_streams:
            stream.write(message)
            stream.flush()

    def flush(self):
        self.real_stream.flush()
        for stream in self.other_streams:
            stream.flush()

    def fileno(self):
        return self.real_stream.fileno()


log_path = path.expanduser(f'~/Scripts/MyScripts/Output/MSM_Pipeline/full_pipeline_log-{datetime.now()}.txt')
makedirs(path.dirname(log_path), exist_ok=True)
log_file = open(log_path, 'w+')
sys.stdout = Tee(sys.__stdout__, log_file)
sys.stderr = Tee(sys.__stderr__, log_file)
Mode = Literal["forward", "reverse", "average"]
Hemisphere = Literal["L", "R"]


# Function for gathering subjects for ciftify
def get_ciftify_subject_list(dataset: str, subjects: list, pattern: str):
    print("\nBegin ciftify subject list generation")
    print('*' * 50)
    print("Finding all files for the following subjects:")
    print(*subjects, sep='\n')
    subject_dirs = []

    for subject in subjects:
        subject_pattern = pattern.replace('#', subject)
        subject_pattern = compile(subject_pattern)
        for entry in listdir(dataset):
            full_path = path.join(dataset, entry)
            if path.isdir(full_path) and subject_pattern.match(entry) and entry not in subject_dirs:
                subject_dirs.append(entry)
                
    user_home = path.expanduser("~")
    ciftify_scripts_path = path.join(user_home, "Scripts", "MyScripts", "Output", "MSM_Pipeline", "ciftify_scripts")
    makedirs(ciftify_scripts_path, exist_ok=True)
    subject_list_file = path.join(ciftify_scripts_path, "ciftify_subjects.txt")
    with open(subject_list_file, "w") as f:
        f.writelines([subject_dir + "\n" for subject_dir in subject_dirs])
    
    print(f"The following subject directories written to {subject_list_file}:")    
    print(sorted(subject_dirs))


# Function to check number of slurm jobs remaining
def is_slurm_queue_open(slurm_user: str, slurm_job_limit: int=500):
    print(f"\nChecking slurm queue for {slurm_user}")
    jobs = check_output(
        ["squeue",
         f"-u{slurm_user}",
         "-o '%.10i %.9p %40j %.8u %.10T %.10M %.6D %R'", "-a"]).decode("utf-8")
    user_home = path.expanduser('~')
    output_dir = rf"{user_home}/Scripts/MyScripts/Output/MSM_Pipeline"

    makedirs(output_dir, exist_ok=True)
    with open(rf"{user_home}/Scripts/MyScripts/Output/MSM_Pipeline/queue.txt", 'w+') as f:
        f.write(jobs)
    with open(rf"{user_home}/Scripts/MyScripts/Output/MSM_Pipeline/queue.txt", 'r') as f:
        jobs = (sum(1 for line in f)) - 1
    open_jobs = slurm_job_limit - jobs
    if open_jobs > 0:
        print(f"{open_jobs} jobs currently open")

    return open_jobs


# Function for running ciftify on list of subjects
def run_ciftify(dataset: str, delimiter: str, subject_index: int, time_index: int,
                output_path: str, slurm_account: str | None, slurm_user: str | None,
                slurm_email: str | None, slurm_job_limit: int | None, is_local: bool=False):
    print("\nStarting ciftify runs")
    print('*' * 50)
    user_home = path.expanduser('~')
    temp_output = path.join(user_home, "Scripts", "MyScripts", "Output",
                            "MSM_Pipeline", "ciftify_scripts")
    makedirs(temp_output, exist_ok=True)
    subject_list_file = path.join(temp_output, "ciftify_subjects.txt")
    with open(subject_list_file, "r") as f:
        directories = [line.strip() for line in f if line.strip()]
    remove(subject_list_file)
    print(f"Subjects loaded from file {subject_list_file}")
    for directory in directories:
        fields = directory.split(delimiter)
        subject = fields[subject_index]
        time_point = fields[time_index]
        subject_output_path = path.join(
            output_path, f"Subject_{subject}_{time_point}")
        makedirs(subject_output_path, exist_ok=True)
        print(
            f"\nCiftify run for subject {subject} at time point {time_point}")
        script_dir = path.dirname(path.realpath(__file__))
        if is_local:
            template_path = path.join(script_dir, "Templates", "Ciftify_template_local.txt")
            with open(template_path, 'r') as f:
                template_read = f.read()
            template = Template(template_read)
            to_write = template.substitute(dataset=dataset, output_dir=subject_output_path, dir=directory, user_home=user_home)
        else:
            template_path = path.join(script_dir, "Templates", "Ciftify_template.txt")
            with open(template_path, 'r') as f:
                template_read = f.read()
            template = Template(template_read)
            to_write = template.substitute(subject=subject, time_point=time_point,
                                        account=slurm_account, email=slurm_email, dataset=dataset,
                                        output_dir=subject_output_path, dir=directory, user_home=user_home)
            

        with open(fr"{temp_output}/Subject_{subject}_{time_point}_recon_all.sh", 'w') as f:
            f.write(to_write)
        print(fr"Script wrote to {temp_output}/Subject_{subject}_{time_point}_recon_all.sh")

        if is_local:
            run(fr"bash {temp_output}/Subject_{subject}_{time_point}_recon_all.sh", shell=True, stdout=sys.stdout, stderr=sys.stderr)
        else:
            if slurm_job_limit != None:
                jobs_open = is_slurm_queue_open(slurm_user, slurm_job_limit)
            else:
                jobs_open = is_slurm_queue_open(slurm_user)
            while jobs_open <= 0:
                sleep(2 * 3600)
                if slurm_job_limit != None:
                    jobs_open = is_slurm_queue_open(slurm_user, slurm_job_limit)
                else:
                    jobs_open = is_slurm_queue_open(slurm_user)
            run(fr"sbatch {temp_output}/Subject_{subject}_{time_point}_recon_all.sh", shell=True, stdout=sys.stdout, stderr=sys.stderr)
        
        remove(fr"{temp_output}/Subject_{subject}_{time_point}_recon_all.sh")


# Helper function for sorting time points
def sort_time_points(time_points: list, number_start_character: int, starting_time=None):
    copy = time_points.copy()
    if starting_time is not None and starting_time in time_points:
        copy.pop(time_points.index(starting_time))

    copy.sort(key=lambda time_point: int(
        time_point[number_start_character:]))

    if starting_time is not None and starting_time in time_points:
        copy.insert(0, starting_time)

    return copy


# Function to get all time points for a subject
def get_subject_time_points(dataset: str, subject: str, alphanumeric_timepoints: bool=False, time_point_number_start_character: int | None=None, starting_time=None):
    print(f"\nSerching for time points for subject {subject}")
    subject_dirs = []
    time_points = []
    pattern = compile(fr"Subject_{subject}_.*")
    for entry in listdir(dataset):
        full_path = path.join(dataset, entry)
        if path.isdir(full_path) and pattern.match(entry):
            subject_dirs.append(entry)

    for directory in subject_dirs:
        fields = directory.split("_")
        time_point = fields[2]
        if time_point not in time_points:
            time_points.append(time_point)

    if alphanumeric_timepoints:
        time_points = sort_time_points(
            time_points, time_point_number_start_character, starting_time)
    else:
        time_points.sort()
    print("The following time points have been located: ", *time_points, sep=' ')
    return time_points


# Helper function for searching files
def find(pattern, search_path):
    for root, dirs, files in walk(search_path):
        for name in files:
            if fnmatch(name, pattern):
                return path.join(root, name)
            

# Helper function for retriving MSM files
def get_files(dataset: str, subject: str, time_point: str):
    # get directory containing data and name prefix
    subject_dir = path.join(dataset, f"Subject_{subject}_{time_point}")
    subdirs = [directory for directory in listdir(subject_dir) if path.isdir(
        path.join(subject_dir, directory)) and directory != "zz_templates"]
    if not subdirs:
        return
    subject_dir = path.join(subject_dir, subdirs[0])
    subject_full_name = subdirs[0]
    
    # get the name of the location of anatomical and spherical surfaces
    subject_thickness_dir = path.join(subject_dir, "T1w", "fsaverage_LR32k")
    subject_curvature_dir = path.join(
        subject_dir, "MNINonLinear", "fsaverage_LR32k")
    left_anatomical_surface = path.join(
        subject_thickness_dir, f"{subject_full_name}.L.midthickness.32k_fs_LR.surf.gii")
    right_anatomical_surface = path.join(
        subject_thickness_dir, f"{subject_full_name}.R.midthickness.32k_fs_LR.surf.gii")
    left_spherical_surface = path.join(
        subject_thickness_dir, f"{subject_full_name}.L.sphere.32k_fs_LR.surf.gii")
    right_spherical_surface = path.join(
        subject_thickness_dir, f"{subject_full_name}.R.sphere.32k_fs_LR.surf.gii")

    # run seperate commands for curvatures
    run(fr"wb_command -cifti-separate {subject_curvature_dir}/{subject_full_name}.thickness.32k_fs_LR.dscalar.nii COLUMN -metric CORTEX_LEFT {subject_curvature_dir}/{subject_full_name}_Thickness.L.func.gii -metric CORTEX_RIGHT {subject_curvature_dir}/{subject_full_name}_Thickness.R.func.gii", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(fr"wb_command -cifti-separate {subject_curvature_dir}/{subject_full_name}.curvature.32k_fs_LR.dscalar.nii COLUMN -metric CORTEX_LEFT {subject_curvature_dir}/{subject_full_name}_Curvature.L.func.gii -metric CORTEX_RIGHT {subject_curvature_dir}/{subject_full_name}_Curvature.R.func.gii", shell=True, stdout=sys.stdout, stderr=sys.stderr)

    # get full path for curvature files
    left_curvature = fr"{subject_curvature_dir}/{subject_full_name}_Curvature.L.func.gii"
    right_curvature = fr"{subject_curvature_dir}/{subject_full_name}_Curvature.R.func.gii"
    
    # get cortex file names
    left_cortex= path.join(subject_curvature_dir, f"{subject_full_name}.L.atlasroi.32k_fs_LR.shape.gii")
    right_cortex= path.join(subject_curvature_dir, f"{subject_full_name}.R.atlasroi.32k_fs_LR.shape.gii")
    
    # get resacled file names
    left_rescaled_surface = path.join(subject_dir, f"{subject_full_name}.L.rescaled.surf.gii")
    right_rescaled_surface = path.join(subject_dir, f"{subject_full_name}.R.rescaled.surf.gii")

    # return all files as list
    subject_files = [left_anatomical_surface, right_anatomical_surface,
                     left_spherical_surface, right_spherical_surface,
                     left_curvature, right_curvature,
                     subject_dir, subject_full_name,
                     left_cortex, right_cortex,
                     left_rescaled_surface, right_rescaled_surface]
    return subject_files


# Generate pre-MSM qc image
def generate_qc_image(dataset: str, subject: str, younger_timepoint: str, older_timepoint: str, output: str, younger_uses_mcribs: bool=False, older_uses_mcribs: bool=False):
    # Get files for qc image
    print("Locating Surfaces")
    if younger_uses_mcribs:
        younger_files = get_files_mcribs(dataset, subject, younger_timepoint)
    else:
        younger_files = get_files(dataset, subject, younger_timepoint)
        
    if older_uses_mcribs:
        older_files = get_files_mcribs(dataset, subject, older_timepoint)
    else:
        older_files = get_files(dataset, subject, older_timepoint)
    
    left_younger_surface = younger_files[0]
    right_younger_surface = younger_files[1]
    left_older_surface = older_files[0]
    right_older_surface = older_files[1]
    
    # create spec file
    print("Creating Spec File")
    spec_file = path.join(
        output, f"{subject}_{younger_timepoint}_to_{older_timepoint}.spec")
    run(f"wb_command -add-to-spec-file {spec_file} CORTEX_LEFT {left_younger_surface}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -add-to-spec-file {spec_file} CORTEX_LEFT {left_older_surface}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -add-to-spec-file {spec_file} CORTEX_RIGHT {right_younger_surface}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -add-to-spec-file {spec_file} CORTEX_RIGHT {right_older_surface}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    
    # create scene file
    print("Creating Scene File")
    script_dir = path.dirname(path.realpath(__file__))
    template_path = path.join(script_dir, "Templates", "pre_msm_qc_template.scene")
    with open(template_path, "r") as f:
        template_read = f.read()
    template = Template(template_read)
    to_write = template.substitute(
        left_younger_surface=left_younger_surface,
        left_older_surface=left_older_surface,
        right_younger_surface=right_younger_surface,
        right_older_surface=right_older_surface
    )
    scene_file = path.join(
        output, f"{subject}_{younger_timepoint}_to_{older_timepoint}.scene")
    with open(scene_file, "w+") as f:
        f.write(to_write)
        
    # generate image
    print("Generating Image")
    image_file = path.join(
        output, f"{subject}_{younger_timepoint}_to_{older_timepoint}.png")
    run(f"wb_command -show-scene {scene_file} 1 {image_file} 1024 512", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    print("QC image written to output directory")

    
# Generate all pre-MSM qc images
def qc_all(dataset: str, output: str,  alphanumeric_timepoints: bool=False, time_point_number_start_character: int | None=None, starting_time=None, uses_mcribs: bool=False):
    print("\nStarting pre-MSM QC image generation")
    print('*' * 50)
    subjects = []
    for directory in listdir(dataset):
        full_path = path.join(dataset, directory)
        fields = directory.split("_")
        subject = fields[1]
        if subject not in subjects:
            subjects.append(subject)
    
    for subject in subjects:
        time_points = get_subject_time_points(dataset, subject, alphanumeric_timepoints, time_point_number_start_character, starting_time)
        if starting_time is not None and starting_time in time_points:
            time_points.remove(starting_time)
            time_points = time_points.sort()
            time_points.insert(0, starting_time)
        for i in range(len(time_points)-1):
            younger_time = time_points[i]
            older_time = time_points[i+1]
            print(f"\nGenerating QC image for subject {subject} from time point {younger_time} to {older_time}")
            if uses_mcribs:
                generate_qc_image(dataset, subject, younger_time, older_time, output, uses_mcribs=True)
            else:
                generate_qc_image(dataset, subject, younger_time, older_time, output)
        
    
# Generate post processing images
def generate_post_processing_image(subject_directory: str, resolution: str, mode: Mode, output: str):
    # extreact info from path
    subject_basename = path.basename(subject_directory)
    subject_basename_list = subject_basename.split("_")
    subject = subject_basename_list[0]
    starting_time = subject_basename_list[1]
    ending_time = subject_basename_list[3]
    
    # get base subject dir for average mode
    if mode == "average":
        subject_directory_base = subject_directory.replace("_avg", "")
        
    # get all files for for post processing
    print("Locating Surfaces")
    if mode == "forward":
        left_younger_surface = path.join(
            subject_directory, f"{subject}_L_{starting_time}-{ending_time}.LYAS.{resolution}.surf.gii")
        right_younger_surface = path.join(
            subject_directory, f"{subject}_R_{starting_time}-{ending_time}.RYAS.{resolution}.surf.gii")
        left_older_surface = path.join(
            subject_directory, f"{subject}_L_{starting_time}-{ending_time}.anat.{resolution}.reg.surf.gii")
        right_older_surface = path.join(
            subject_directory, f"{subject}_R_{starting_time}-{ending_time}.anat.{resolution}.reg.surf.gii")
    elif mode == "reverse":
        left_younger_surface = path.join(
            subject_directory, f"{subject}_L_{starting_time}-{ending_time}.anat.{resolution}.reg.surf.gii")
        right_younger_surface = path.join(
            subject_directory, f"{subject}_R_{starting_time}-{ending_time}.anat.{resolution}.reg.surf.gii")
        left_older_surface = path.join(
            subject_directory, f"{subject}_L_{starting_time}-{ending_time}.LOAS.{resolution}.surf.gii")
        right_older_surface = path.join(
            subject_directory, f"{subject}_R_{starting_time}-{ending_time}.ROAS.{resolution}.surf.gii")
    elif mode == "average":
        left_younger_surface = path.join(
            subject_directory_base, f"{subject}_L_{starting_time}-{ending_time}.LYAS.{resolution}.surf.gii")
        right_younger_surface = path.join(
            subject_directory_base, f"{subject}_R_{starting_time}-{ending_time}.RYAS.{resolution}.surf.gii")
        left_older_surface = path.join(
            subject_directory, f"{subject}_L_{starting_time}-{ending_time}.avgfor.anat.{resolution}.reg.surf.gii")
        right_older_surface = path.join(
            subject_directory, f"{subject}_R_{starting_time}-{ending_time}.avgfor.anat.{resolution}.reg.surf.gii")
        
    
    print("Locating Maps")
    if mode == "average":
        left_surface_map = path.join(
            subject_directory, f"{subject}_L_{starting_time}-{ending_time}.avgfor.surfdist.{resolution}.reg.func.gii")
        right_surface_map = path.join(
            subject_directory, f"{subject}_R_{starting_time}-{ending_time}.avgfor.surfdist.{resolution}.reg.func.gii")
    else:
        left_surface_map = path.join(
            subject_directory, f"{subject}_L_{starting_time}-{ending_time}.surfdist.{resolution}.func.gii")
        right_surface_map = path.join(
            subject_directory, f"{subject}_R_{starting_time}-{ending_time}.surfdist.{resolution}.func.gii")
    spec_file = path.join(
        subject_directory, f"{subject}_{starting_time}-{ending_time}_{resolution}.spec")
    
    # set palette
    print("Setting Palette")
    run(f"wb_command -metric-palette {left_surface_map} MODE_AUTO_SCALE -palette-name raich6_clrmid", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -metric-palette {right_surface_map} MODE_AUTO_SCALE -palette-name raich6_clrmid", shell=True, stdout=sys.stdout, stderr=sys.stderr)

    # add to spec file
    print("Adding to Spec File")
    run(f"wb_command -add-to-spec-file {spec_file} CORTEX_LEFT {left_younger_surface}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -add-to-spec-file {spec_file} CORTEX_LEFT {left_older_surface}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -add-to-spec-file {spec_file} CORTEX_LEFT {left_surface_map}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -add-to-spec-file {spec_file} CORTEX_RIGHT {right_younger_surface}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -add-to-spec-file {spec_file} CORTEX_RIGHT {right_older_surface}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -add-to-spec-file {spec_file} CORTEX_RIGHT {right_surface_map}", shell=True, stdout=sys.stdout, stderr=sys.stderr)

    # create scene file for auto scale
    print("Creating Auto Scale Scene")
    script_dir = path.dirname(path.realpath(__file__))
    if mode == "forward" or mode == "average":
        template_path_auto_scale = path.join(
            script_dir, "Templates", "post_processing_template_forward.scene")
        template_path_set_scale = path.join(
            script_dir, "Templates", "post_processing_set_scale_template_forward.scene")
    elif mode == "reverse":
        template_path_auto_scale = path.join(
            script_dir, "Templates", "post_processing_template_reverse.scene")
        template_path_set_scale = path.join(
            script_dir, "Templates", "post_processing_set_scale_template_forward.scene")
    

    with open(template_path_auto_scale, "r") as f:
        template_read_auto_scale = f.read()
    template_auto_scale = Template(template_read_auto_scale)
    to_write_auto_scale = template_auto_scale.substitute(
        left_younger_surface=left_younger_surface,
        left_older_surface=left_older_surface,
        left_surface_map=left_surface_map,
        right_younger_surface=right_younger_surface,
        right_older_surface=right_older_surface,
        right_surface_map=right_surface_map
    )
    if mode == "average":
        template_auto_scale_output = path.join(
            subject_directory, f"{subject}_{starting_time}-{ending_time}_avg_{resolution}.scene")
    else:
        template_auto_scale_output = path.join(
            subject_directory, f"{subject}_{starting_time}-{ending_time}_{resolution}.scene")
    with open(template_auto_scale_output, "w+") as f:
        f.write(to_write_auto_scale)

    # create scene file for set scale
    print("Creating Set Scale Scene")
    with open(template_path_set_scale, "r") as f:
        template_read_set_scale = f.read()
    template_set_scale = Template(template_read_set_scale)
    to_write_set_scale = template_set_scale.substitute(
        left_younger_surface=left_younger_surface,
        left_older_surface=left_older_surface,
        left_surface_map=left_surface_map,
        right_younger_surface=right_younger_surface,
        right_older_surface=right_older_surface,
        right_surface_map=right_surface_map
    )
    if mode == "average":
        template_set_scale_output = path.join(
            subject_directory, f"{subject}_{starting_time}-{ending_time}_avg_{resolution}_SET-SCALE.scene")
    else:
        template_set_scale_output = path.join(
            subject_directory, f"{subject}_{starting_time}-{ending_time}_{resolution}_SET-SCALE.scene")
    with open(template_set_scale_output, "w+") as f:
        f.write(to_write_set_scale)

    # create post processing folder
    post_processing_dir = path.join(subject_directory, "post_processing")
    makedirs(post_processing_dir, exist_ok=True)
    
    # generate images
    print("Generating Images")
    if mode=="average":
        scene_auto_scale = path.join(
            subject_directory, f"{subject}_{starting_time}-{ending_time}_avg_{resolution}.scene")
        scene_set_scale = path.join(
            subject_directory, f"{subject}_{starting_time}-{ending_time}_avg_{resolution}_SET-SCALE.scene")
        image_auto_scale = path.join(
            post_processing_dir, f"{subject}_{starting_time}-{ending_time}_avg_{resolution}.png")
        image_set_scale = path.join(
            post_processing_dir, f"{subject}_{starting_time}-{ending_time}_avg_{resolution}SET-SCALE.png")
    else:    
        scene_auto_scale = path.join(
            subject_directory, f"{subject}_{starting_time}-{ending_time}_{resolution}.scene")
        scene_set_scale = path.join(
            subject_directory, f"{subject}_{starting_time}-{ending_time}_{resolution}_SET-SCALE.scene")
        image_auto_scale = path.join(
            post_processing_dir, f"{subject}_{starting_time}-{ending_time}_{resolution}.png")
        image_set_scale = path.join(
            post_processing_dir, f"{subject}_{starting_time}-{ending_time}_{resolution}SET-SCALE.png")
        
    run(f"wb_command -show-scene {scene_auto_scale} 1 {image_auto_scale} 1024 512", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -show-scene {scene_set_scale} 1 {image_set_scale} 1024 512", shell=True, stdout=sys.stdout, stderr=sys.stderr)

    # ensure output exists
    makedirs(output, exist_ok=True)
    
    # copy images to output
    print("Copying Images to Output")
    copy2(image_auto_scale, output)
    copy2(image_set_scale, output)


# Function to run post processing on all subjects
def post_process_all(dataset: str, starting_time: str, resolution: str, output: str):
    for directory in listdir(dataset):
        full_path = path.join(dataset, directory)
        fields = directory.split("_")
        subject = fields[0]
        first_time = fields[1]
        second_time = fields[3]
        if first_time.isalpha():
            first_month = first_time
        else:
            first_month = int(sub("[^0-9]", "", first_time))
        if second_time.isalpha():
            second_month = second_time
        else:
            second_month = int(sub("[^0-9]", "", second_time))
        is_avg = True if "avg" in directory else False
       
        subject_output = path.join(output, subject)
        makedirs(subject_output, exist_ok=True)
        print("*" * 50)
        print(f"Begin Post Processing at {resolution} resolution")
        print("*" * 50)
        print(
            f"Path: {full_path}\nSubject: {subject}\nStarting Time: {starting_time}\nTime1: {first_time}\nTime2: {second_time}\nAverage: {is_avg}\nOutput: {subject_output}")
        if "avg" in directory:
            print("Mode: Average")
            generate_post_processing_image(full_path,
                                           resolution,
                                           "average",
                                           subject_output)
        
        elif first_time == starting_time:
            print("Mode: Forward")
            generate_post_processing_image(full_path,
                                           resolution,
                                           "forward",
                                           subject_output)

        elif second_time == starting_time:
            print("Mode: Reverse")
            generate_post_processing_image(full_path,
                                           resolution,
                                           "reverse",
                                           subject_output)

        elif int(first_month) < int(second_month):
            print("Mode: Forward")
            generate_post_processing_image(full_path,
                                           resolution,
                                           "forward",
                                           subject_output)

        elif int(first_month) > int(second_month):
            print("Mode: Reverse")
            generate_post_processing_image(full_path,
                                           resolution,
                                           "reverse",
                                           subject_output)


# helper function for retriving subjects
def get_subjects(dataset: str):
    subjects = []
    print("RETRIVING LIST OF SUBJECTS")
    print("*" * 50)
    for directory in listdir(dataset):
        full_path = path.join(dataset, directory)
        if path.isdir(full_path):
            fields = directory.split("_")
            subject = fields[1]
            if subject not in subjects:
                print(f"Found subject number {subject}")
                subjects.append(subject)
    subjects.sort()
    return subjects


# Function for running MSM commands
def run_msm(dataset: str, output: str, subject: str, younger_timepoint: str,
            older_timepoint: str, mode: Mode, younger_uses_mcribs: bool=False, older_uses_mcribs: bool=False,
            is_local: bool=False, hemisphere: Hemisphere | None=None, levels: int=6, config: str | None=None, 
            max_anat: str | None=None, max_cp: str | None=None, slurm_email: str | None=None, slurm_account: str | None=None,
            slurm_user: str | None=None, slurm_job_limit: int | None=None, use_rescaled: bool=False):
    print(f"\nStarting MSM run for subject {subject} from time point {younger_timepoint} to {older_timepoint} in {mode} mode")
    print('*' * 50)
    
    user_home = path.expanduser('~')
    script_dir = path.dirname(path.realpath(__file__))
    if config == None:
        print("No config file provided, using default")
        config = path.join(script_dir, "NeededFiles", "configAnatGrid6")
    if max_anat == None:
        print("No max_anat provided, using default")
        max_anat = path.join(script_dir, "NeededFiles", "ico6sphere.LR.reg.surf.gii")
    if max_cp == None:
        print("No max_cp provided, using default")
        max_cp = path.join(script_dir, "NeededFiles", "ico5sphere.LR.reg.surf.gii")
        
    print(f"Mode is set to {mode}, Subject is {subject}, Younger Timepoint is {younger_timepoint}, Older Timepoint is {older_timepoint}")
    if is_local and hemisphere is None:
        print("Local mode selected but no hemisphere provided, exiting")
        return
    
    if mode == "forward":
        temp_output = path.join(user_home, "Scripts", "MyScripts", "Output", "MSM_Pipeline",
                                "MSM_scripts", fr"{subject}_{younger_timepoint}_to_{older_timepoint}")
    elif mode == "reverse":
        temp_output = path.join(user_home, "Scripts", "MyScripts", "Output", "MSM_Pipeline",
                                "MSM_scripts", fr"{subject}_{older_timepoint}_to_{younger_timepoint}")
    print(f"Creating the following script directory: {temp_output}")
    makedirs(temp_output, exist_ok=True)

    print(
        f"\nRetriving files for time points {younger_timepoint} and {older_timepoint}")
    if younger_uses_mcribs:
        print("Using mcribs naming conventions for younger timepoint")
        younger_files = get_files_mcribs(dataset, subject, younger_timepoint)
        
        print("Using rescaled surfaces")
        left_younger_anatomical_surface = younger_files[10]
        right_younger_anatomical_surface = younger_files[11]
        
        print("matching icosphere to mcribs data")
        left_younger_midthickness = younger_files[0]
        right_younger_midthickness = younger_files[1]
        
        left_younger_smoothed = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.midthickness.smoothed.surf.gii")
        right_younger_smoothed = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.midthickness.smoothed.surf.gii")
        
        left_younger_inflated = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.inflated.surf.gii")
        right_younger_inflated = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.inflated.surf.gii")
        
        left_younger_matched = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.matched.surf.gii")
        right_younger_matched = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.matched.surf.gii")
        
        left_younger_spherical_surface = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.sphere.surf.gii")
        right_younger_spherical_surface = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.sphere.surf.gii")
        
        print("Smoothing midthickness")
        run(f'wb_command -surface-smoothing {left_younger_midthickness} 1 10000 {left_younger_smoothed}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        run(f'wb_command -surface-smoothing {right_younger_midthickness} 1 10000 {right_younger_smoothed}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        
        print("Inflating smoothed surfaces")
        run(f'wb_command -surface-inflation {left_younger_smoothed} {left_younger_smoothed} 10 1 100 2 {left_younger_inflated}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        run(f'wb_command -surface-inflation {right_younger_smoothed} {right_younger_smoothed} 10 1 100 2 {right_younger_inflated}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        
        print("Matching inflated to icosphere")
        run(f'wb_command -surface-match {max_anat} {left_younger_inflated} {left_younger_matched}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        run(f'wb_command -surface-match {max_anat} {right_younger_inflated} {right_younger_matched}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        
        print("Centering matched sphere")
        run(f'wb_command -surface-modify-sphere -recenter {left_younger_matched} 100 {left_younger_spherical_surface}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        run(f'wb_command -surface-modify-sphere -recenter {right_younger_matched} 100 {right_younger_spherical_surface}', shell=True, stdout=sys.stdout, stderr=sys.stderr)   
    else:
        print("Using standard naming conventions for younger timepoint")
        younger_files = get_files(dataset, subject, younger_timepoint)
        if use_rescaled:
            print("Using rescaled surfaces for younger timepoint")
            left_younger_anatomical_surface = younger_files[10]
            right_younger_anatomical_surface = younger_files[11]
            
            print("matching icosphere to rescaled data")
            left_younger_midthickness = younger_files[0]
            right_younger_midthickness = younger_files[1]
            
            left_younger_smoothed = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.midthickness.smoothed.surf.gii")
            right_younger_smoothed = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.midthickness.smoothed.surf.gii")
            
            left_younger_inflated = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.inflated.surf.gii")
            right_younger_inflated = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.inflated.surf.gii")
            
            left_younger_matched = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.matched.surf.gii")
            right_younger_matched = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.matched.surf.gii")
            
            left_younger_spherical_surface = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.sphere.surf.gii")
            right_younger_spherical_surface = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.sphere.surf.gii")
            
            print("Smoothing midthickness")
            run(f'wb_command -surface-smoothing {left_younger_midthickness} 1 10000 {left_younger_smoothed}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            run(f'wb_command -surface-smoothing {right_younger_midthickness} 1 10000 {right_younger_smoothed}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            
            print("Inflating smoothed surfaces")
            run(f'wb_command -surface-inflation {left_younger_smoothed} {left_younger_smoothed} 10 1 100 2 {left_younger_inflated}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            run(f'wb_command -surface-inflation {right_younger_smoothed} {right_younger_smoothed} 10 1 100 2 {right_younger_inflated}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            
            print("Matching inflated to icosphere")
            run(f'wb_command -surface-match {max_anat} {left_younger_inflated} {left_younger_matched}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            run(f'wb_command -surface-match {max_anat} {right_younger_inflated} {right_younger_matched}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            
            print("Centering matched sphere")
            run(f'wb_command -surface-modify-sphere -recenter {left_younger_matched} 100 {left_younger_spherical_surface}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            run(f'wb_command -surface-modify-sphere -recenter {right_younger_matched} 100 {right_younger_spherical_surface}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        else:
            print("Using base surfacecs for younger timepoint")
            left_younger_anatomical_surface = younger_files[0]
            right_younger_anatomical_surface = younger_files[1]
        
        left_younger_spherical_surface = younger_files[2]
        right_younger_spherical_surface = younger_files[3]
        
    if older_uses_mcribs:
        print("Using mcribs naming conventions for older timepoint")
        older_files = get_files_mcribs(dataset, subject, older_timepoint)
        
        left_older_anatomical_surface = older_files[10]
        right_older_anatomical_surface = older_files[11]
        
        print("Matching icosphere to mcribs data")
        left_older_midthickness = older_files[0]
        right_older_midthickness = older_files[1]
        
        left_older_smoothed = path.join(dataset, f"Subject_{subject}_{older_timepoint}", "lh.midthickness.smoothed.surf.gii")
        right_older_smoothed = path.join(dataset, f"Subject_{subject}_{older_timepoint}", "rh.midthickness.smoothed.surf.gii")
        
        left_older_inflated = path.join(dataset, f"Subject_{subject}_{older_timepoint}", "lh.inflated.surf.gii")
        right_older_inflated = path.join(dataset, f"Subject_{subject}_{older_timepoint}", "rh.inflated.surf.gii")
        
        left_older_matched = path.join(dataset, f"Subject_{subject}_{older_timepoint}", "lh.matched.surf.gii")
        right_older_matched = path.join(dataset, f"Subject_{subject}_{older_timepoint}", "rh.matched.surf.gii")
        
        left_older_spherical_surface = path.join(dataset, f"Subject_{subject}_{older_timepoint}", "lh.sphere.surf.gii")
        right_older_spherical_surface = path.join(dataset, f"Subject_{subject}_{older_timepoint}", "rh.sphere.surf.gii")
        
        print("Smoothing midthickness")
        run(f'wb_command -surface-smoothing {left_older_midthickness} 1 10000 {left_older_smoothed}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        run(f'wb_command -surface-smoothing {right_older_midthickness} 1 10000 {right_older_smoothed}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        
        print("Inflating smoothed surfaces")
        run(f'wb_command -surface-inflation {left_older_smoothed} {left_older_smoothed} 10 1 100 2 {left_older_inflated}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        run(f'wb_command -surface-inflation {right_older_smoothed} {right_older_smoothed} 10 1 100 2 {right_older_inflated}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        
        print("Matching inflated to icosphere")
        run(f'wb_command -surface-match {max_anat} {left_older_inflated} {left_older_matched}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        run(f'wb_command -surface-match {max_anat} {right_older_inflated} {right_older_matched}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        
        print("Centering matched sphere")
        run(f'wb_command -surface-modify-sphere -recenter {left_older_matched} 100 {left_older_spherical_surface}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        run(f'wb_command -surface-modify-sphere -recenter {right_older_matched} 100 {right_older_spherical_surface}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
    else:
        print("Using standard naming conventions for older timepoint")
        older_files = get_files(dataset, subject, older_timepoint)
        if use_rescaled:
            print("Using rescaled surfaces for older timepoint")
            left_younger_anatomical_surface = younger_files[10]
            right_younger_anatomical_surface = younger_files[11]
            
            print("matching icosphere to rescaled data")
            left_younger_midthickness = younger_files[0]
            right_younger_midthickness = younger_files[1]
            
            left_younger_smoothed = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.midthickness.smoothed.surf.gii")
            right_younger_smoothed = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.midthickness.smoothed.surf.gii")
            
            left_younger_inflated = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.inflated.surf.gii")
            right_younger_inflated = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.inflated.surf.gii")
            
            left_younger_matched = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.matched.surf.gii")
            right_younger_matched = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.matched.surf.gii")
            
            left_younger_spherical_surface = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "lh.sphere.surf.gii")
            right_younger_spherical_surface = path.join(dataset, f"Subject_{subject}_{younger_timepoint}", "rh.sphere.surf.gii")
            
            print("Smoothing midthickness")
            run(f'wb_command -surface-smoothing {left_younger_midthickness} 1 10000 {left_younger_smoothed}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            run(f'wb_command -surface-smoothing {right_younger_midthickness} 1 10000 {right_younger_smoothed}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            
            print("Inflating smoothed surfaces")
            run(f'wb_command -surface-inflation {left_younger_smoothed} {left_younger_smoothed} 10 1 100 2 {left_younger_inflated}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            run(f'wb_command -surface-inflation {right_younger_smoothed} {right_younger_smoothed} 10 1 100 2 {right_younger_inflated}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            
            print("Matching inflated to icosphere")
            run(f'wb_command -surface-match {max_anat} {left_younger_inflated} {left_younger_matched}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            run(f'wb_command -surface-match {max_anat} {right_younger_inflated} {right_younger_matched}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            
            print("Centering matched sphere")
            run(f'wb_command -surface-modify-sphere -recenter {left_younger_matched} 100 {left_younger_spherical_surface}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
            run(f'wb_command -surface-modify-sphere -recenter {right_younger_matched} 100 {right_younger_spherical_surface}', shell=True, stdout=sys.stdout, stderr=sys.stderr)
        else:
            print("Using base surfaces for older timepoint")
            left_older_anatomical_surface = older_files[0]
            right_older_anatomical_surface = older_files[1]
        left_older_spherical_surface = older_files[2]
        right_older_spherical_surface = older_files[3]

    left_younger_curvature = younger_files[4]
    right_younger_curvature = younger_files[5]
    left_older_curvature = older_files[4]
    right_older_curvature = older_files[5]

    if not younger_files or not older_files:
        print("no files found skipping this run")
        return

    print("Younger time point files:", *younger_files, sep='\n')
    print("Older time point files:", *older_files, sep="\n")

    if mode == "forward":
        output = path.join(output, fr"{subject}_{younger_timepoint}_to_{older_timepoint}")
        makedirs(output, exist_ok=True)
        left_file_prefix = fr"{output}/{subject}_L_{younger_timepoint}-{older_timepoint}."
        right_file_prefix = fr"{output}/{subject}_R_{younger_timepoint}-{older_timepoint}."

        print(" \n")
        print(fr"Generating script file {temp_output}/Subject_{subject}_L_{younger_timepoint}-{older_timepoint}_MSM.sh")
        script_dir = path.dirname(path.realpath(__file__))
        
        # Templates for remote run (default)
        if not is_local:
            # left hemisphere
            template_path_l = path.join(script_dir, "Templates", "MSM_template_forward_L.txt")
            with open(template_path_l, "r") as f:
                template_read_l = f.read()
            template_l = Template(template_read_l)
            to_write_l = template_l.substitute(
                subject=subject, starting_time=younger_timepoint, ending_time=older_timepoint,
                user_home=user_home, email=slurm_email, account=slurm_account, levels=levels,
                config=config, yss=left_younger_spherical_surface, oss=left_older_spherical_surface, yc=left_younger_curvature,
                oc=left_older_curvature, yas=left_younger_anatomical_surface, oas=left_older_anatomical_surface,
                f_out=left_file_prefix, maxanat=max_anat, maxcp=max_cp)
            with open(fr"{temp_output}/Subject_{subject}_L_{younger_timepoint}-{older_timepoint}_MSM.sh", "w+") as f:
                    f.write(to_write_l)
            
            # right hemisphere
            template_path_r = path.join(script_dir, "Templates", "MSM_template_forward_R.txt")
            with open(template_path_r, "r") as f:
                template_read_r = f.read()
            template_r = Template(template_read_r)
            to_write_r = template_r.substitute(
                subject=subject, starting_time=younger_timepoint, ending_time=older_timepoint,
                user_home=user_home, email=slurm_email, account=slurm_account, levels=levels,
                config=config, yss=right_younger_spherical_surface, oss=right_older_spherical_surface, yc=right_younger_curvature,
                oc=right_older_curvature, yas=right_younger_anatomical_surface, oas=right_older_anatomical_surface,
                f_out=right_file_prefix, maxanat=max_anat, maxcp=max_cp)
            with open(fr"{temp_output}/Subject_{subject}_R_{younger_timepoint}-{older_timepoint}_MSM.sh", "w+") as f:
                    f.write(to_write_r)
                    
                    
        # Templates for local run
        elif is_local:
            if hemisphere == "L":
                # left hemisphere
                template_path_l = path.join(script_dir, "Templates", "MSM_template_forward_L_local.txt")
                with open(template_path_l, "r") as f:
                    template_read_l = f.read()
                template_l = Template(template_read_l)
                to_write_l = template_l.substitute(
                    levels=levels, config=config, yss=left_younger_spherical_surface, oss=left_older_spherical_surface, yc=left_younger_curvature,
                    oc=left_older_curvature, yas=left_younger_anatomical_surface, oas=left_older_anatomical_surface,
                    f_out=left_file_prefix, maxanat=max_anat, maxcp=max_cp)
                with open(fr"{temp_output}/Subject_{subject}_L_{younger_timepoint}-{older_timepoint}_MSM.sh", "w+") as f:
                    f.write(to_write_l)
                    
            elif hemisphere == "R":
            # right hemisphere
                template_path_r = path.join(script_dir, "Templates", "MSM_template_forward_R_local.txt")
                with open(template_path_r, "r") as f:
                    template_read_r = f.read()
                template_r = Template(template_read_r)
                to_write_r = template_r.substitute(
                    levels=levels, config=config, yss=right_younger_spherical_surface, oss=right_older_spherical_surface, yc=right_younger_curvature,
                    oc=right_older_curvature, yas=right_younger_anatomical_surface, oas=right_older_anatomical_surface,
                    f_out=right_file_prefix, maxanat=max_anat, maxcp=max_cp)
                with open(fr"{temp_output}/Subject_{subject}_R_{younger_timepoint}-{older_timepoint}_MSM.sh", "w+") as f:
                    f.write(to_write_r)

        # submit remote jobs
        if not is_local:
            #left hemisphere
            if slurm_job_limit == None:
                jobs_open = is_slurm_queue_open(slurm_user)
            else:
                jobs_open = is_slurm_queue_open(slurm_user, slurm_job_limit)
            while jobs_open <= 0:
                print("no jobs open waiting 2 hours")
                sleep(2 * 3600)
                if slurm_job_limit == None:
                    jobs_open = is_slurm_queue_open(slurm_user)
                else:
                    jobs_open = is_slurm_queue_open(slurm_user, slurm_job_limit)
            print("Jobs open submitting script")
            run(fr"sbatch {temp_output}/Subject_{subject}_L_{younger_timepoint}-{older_timepoint}_MSM.sh", shell=True, stdout=sys.stdout, stderr=sys.stderr)
            remove(fr"{temp_output}/Subject_{subject}_L_{younger_timepoint}-{older_timepoint}_MSM.sh")
            
            #right hemisphere
            if slurm_job_limit == None:
                jobs_open = is_slurm_queue_open(slurm_user)
            else:
                jobs_open = is_slurm_queue_open(slurm_user, slurm_job_limit)
            
            while jobs_open <= 0:
                print("no jobs open waiting 2 hours")
                sleep(2 * 3600)
                if slurm_job_limit == None:
                    jobs_open = is_slurm_queue_open(slurm_user)
                else:
                    jobs_open = is_slurm_queue_open(slurm_user, slurm_job_limit)
            print("Jobs open submitting script")
            run(fr"sbatch {temp_output}/Subject_{subject}_R_{younger_timepoint}-{older_timepoint}_MSM.sh", shell=True, stdout=sys.stdout, stderr=sys.stderr)
            remove(fr"{temp_output}/Subject_{subject}_R_{younger_timepoint}-{older_timepoint}_MSM.sh")
        
         # run lcoal job        
        elif is_local:
            if hemisphere == "L":
                run(fr"bash {temp_output}/Subject_{subject}_L_{younger_timepoint}-{older_timepoint}_MSM.sh", shell=True, stdout=sys.stdout, stderr=sys.stderr)
                remove(fr"{temp_output}/Subject_{subject}_L_{younger_timepoint}-{older_timepoint}_MSM.sh")
            elif hemisphere == "R":
                run(fr"bash {temp_output}/Subject_{subject}_R_{younger_timepoint}-{older_timepoint}_MSM.sh", shell=True, stdout=sys.stdout, stderr=sys.stderr)
                remove(fr"{temp_output}/Subject_{subject}_R_{younger_timepoint}-{older_timepoint}_MSM.sh")

    elif mode == "reverse":
        output = path.join(
            output, fr"{subject}_{older_timepoint}_to_{younger_timepoint}")
        makedirs(output, exist_ok=True)
        left_file_prefix = fr"{output}/{subject}_L_{older_timepoint}-{younger_timepoint}."
        right_file_prefix = fr"{output}/{subject}_R_{older_timepoint}-{younger_timepoint}."
        print(" \n")
        print(fr"Generating script {temp_output}/Subject_{subject}_L_{older_timepoint}-{younger_timepoint}_MSM.sh")
        script_dir = path.dirname(path.realpath(__file__))
        # Templates for remote jobs
        if not is_local:
            #left hemisphere
            template_path_l = path.join(script_dir, "Templates", "MSM_template_reverse_L.txt")
            with open(template_path_l, "r") as f:
                template_read_l = f.read()
            template_l = Template(template_read_l)
            to_write_l = template_l.substitute(
                subject=subject, starting_time=older_timepoint, ending_time=younger_timepoint,
                user_home=user_home, email=slurm_email, account=slurm_account, levels=levels,
                config=config, yss=left_younger_spherical_surface, oss=left_older_spherical_surface, yc=left_younger_curvature,
                oc=left_older_curvature, yas=left_younger_anatomical_surface, oas=left_older_anatomical_surface,
                r_out=left_file_prefix, maxanat=max_anat, maxcp=max_cp)
            with open(fr"{temp_output}/Subject_{subject}_L_{older_timepoint}-{younger_timepoint}_MSM.sh", "w+") as f:
                    f.write(to_write_l)
            
            #right hemisphere
            template_path_r = path.join(script_dir, "Templates", "MSM_template_reverse_R.txt")
            with open(template_path_r, "r") as f:
                template_read_r = f.read()
            template_r = Template(template_read_r)
            to_write_r = template_r.substitute(
                subject=subject, starting_time=older_timepoint, ending_time=younger_timepoint,
                user_home=user_home, email=slurm_email, account=slurm_account, levels=levels,
                config=config, yss=right_younger_spherical_surface, oss=right_older_spherical_surface, yc=right_younger_curvature,
                oc=right_older_curvature, yas=right_younger_anatomical_surface, oas=right_older_anatomical_surface,
                r_out=right_file_prefix, maxanat=max_anat, maxcp=max_cp)
            with open(fr"{temp_output}/Subject_{subject}_R_{older_timepoint}-{younger_timepoint}_MSM.sh", "w+") as f:
                    f.write(to_write_r)
            
        # Templates for local jobs
        elif is_local:
            # left_hemisphere
            if hemisphere == "L":
                template_path_l = path.join(script_dir, "Templates", "MSM_template_reverse_L_local.txt")
                with open(template_path_l, "r") as f:
                    template_read_l = f.read()
                template_l = Template(template_read_l)
                to_write_l = template_l.substitute(
                    levels=levels, config=config, yss=left_younger_spherical_surface, oss=left_older_spherical_surface, yc=left_younger_curvature,
                    oc=left_older_curvature, yas=left_younger_anatomical_surface, oas=left_older_anatomical_surface,
                    r_out=left_file_prefix, maxanat=max_anat, maxcp=max_cp)
                with open(fr"{temp_output}/Subject_{subject}_L_{older_timepoint}-{younger_timepoint}_MSM.sh", "w+") as f:
                    f.write(to_write_l)
            
            # right_hemisphere
            elif hemisphere == "R":
                template_path_r = path.join(script_dir, "Templates", "MSM_template_reverse_R_local.txt")
                with open(template_path_r, "r") as f:
                    template_read_r = f.read()
                template_r = Template(template_read_r)
                to_write_r = template_r.substitute(
                    levels=levels, config=config, yss=right_younger_spherical_surface, oss=right_older_spherical_surface, yc=right_younger_curvature,
                    oc=right_older_curvature, yas=right_younger_anatomical_surface, oas=right_older_anatomical_surface,
                    r_out=right_file_prefix, maxanat=max_anat, maxcp=max_cp)
                with open(fr"{temp_output}/Subject_{subject}_R_{older_timepoint}-{younger_timepoint}_MSM.sh", "w+") as f:
                    f.write(to_write_r)
         
        # Submit remote jobs
        if not is_local:
            # Left hemisphere
            if slurm_job_limit == None:
                jobs_open = is_slurm_queue_open(slurm_user)
            else:
                jobs_open = is_slurm_queue_open(slurm_user, slurm_job_limit)
            
            while jobs_open <= 0:
                print("no jobs open waiting 2 hours")
                sleep(2 * 3600)
                if slurm_job_limit == None:
                    jobs_open = is_slurm_queue_open(slurm_user)
                else:
                    jobs_open = is_slurm_queue_open(slurm_user, slurm_job_limit)
            print("Jobs open submitting script")
            run(fr"sbatch {temp_output}/Subject_{subject}_L_{older_timepoint}-{younger_timepoint}_MSM.sh", shell=True, stdout=sys.stdout, stderr=sys.stderr)
            remove(fr"{temp_output}/Subject_{subject}_L_{older_timepoint}-{younger_timepoint}_MSM.sh")
            
            # Right hemisphere
            if slurm_job_limit == None:
                jobs_open = is_slurm_queue_open(slurm_user)
            else:
                jobs_open = is_slurm_queue_open(slurm_user, slurm_job_limit)
            
            while jobs_open <= 0:
                print("no jobs open waiting 2 hours")
                sleep(2 * 3600)
                if slurm_job_limit == None:
                    jobs_open = is_slurm_queue_open(slurm_user)
                else:
                    jobs_open = is_slurm_queue_open(slurm_user, slurm_job_limit)
            print("Jobs open submitting script")
            run(fr"sbatch {temp_output}/Subject_{subject}_R_{older_timepoint}-{younger_timepoint}_MSM.sh", shell=True, stdout=sys.stdout, stderr=sys.stderr)
            remove(fr"{temp_output}/Subject_{subject}_R_{older_timepoint}-{younger_timepoint}_MSM.sh")

        # Run local jobs
        if is_local:
            if hemisphere == "L":
                run(fr"bash {temp_output}/Subject_{subject}_L_{older_timepoint}-{younger_timepoint}_MSM.sh", shell=True, stdout=sys.stdout, stderr=sys.stderr)
                remove(fr"{temp_output}/Subject_{subject}_L_{older_timepoint}-{younger_timepoint}_MSM.sh")
            
            elif hemisphere == "R":
                run(fr"bash {temp_output}/Subject_{subject}_R_{older_timepoint}-{younger_timepoint}_MSM.sh", shell=True, stdout=sys.stdout, stderr=sys.stderr)
                remove(fr"{temp_output}/Subject_{subject}_R_{older_timepoint}-{younger_timepoint}_MSM.sh")
            

# Function for MSM BL to all
def run_msm_bl_to_all(dataset: str, output: str, starting_time: str, slurm_account: str, slurm_user: str,
                      slurm_email: str, alphanumeric_timepoints: bool=False, time_point_number_start_character: int | None=None,
                      younger_uses_mcribs: bool=False, older_uses_mcribs: bool=False, slurm_job_limit: int | None=None, levels: int=6, config: str | None=None,
                      max_anat: str | None=None, max_cp: str | None=None, use_rescaled: bool=False):

    subjects = get_subjects(dataset)
    print("\nAll subjects found. Beginning MSM")
    print('*' * 50)
    for subject in subjects:
        time_points = get_subject_time_points(
            dataset, subject, alphanumeric_timepoints, time_point_number_start_character, starting_time)
        if starting_time not in time_points:
            print(
                f"ERROR: Starting Time missing for {subject}! Proceeding to next subject")
            continue

        for time_point in time_points:
            if time_point != starting_time:
                run_msm(dataset=dataset, output=output, subject=subject, younger_timepoint=starting_time, older_timepoint=time_point,
                        mode="forward", younger_uses_mcribs=younger_uses_mcribs, older_uses_mcribs=older_uses_mcribs, levels=levels,
                        config=config, max_anat=max_anat, max_cp=max_cp, slurm_email=slurm_email, slurm_account=slurm_account,
                        slurm_user=slurm_user, slurm_job_limit=slurm_job_limit, use_rescaled=use_rescaled)
                run_msm(dataset=dataset, output=output, subject=subject, younger_timepoint=starting_time, older_timepoint=time_point,
                        mode="reverse", younger_uses_mcribs=younger_uses_mcribs, older_uses_mcribs=older_uses_mcribs, levels=levels,
                        config=config, max_anat=max_anat, max_cp=max_cp, slurm_email=slurm_email, slurm_account=slurm_account,
                        slurm_user=slurm_user, slurm_job_limit=slurm_job_limit, use_rescaled=use_rescaled)


# Function to run MSM on shirt time windows
def run_msm_short_time_windows(dataset: str, output: str, slurm_account: str, slurm_user: str, slurm_email: str, 
                               alphanumeric_timepoints: bool = False, time_point_number_start_character: int | None=None,
                               younger_uses_mcribs: bool=False, older_uses_mcribs: bool=False, slurm_job_limit: int | None=None, levels: int=6,
                               config: str | None=None, max_anat: str | None=None, max_cp: str | None=None,
                               starting_time: str | None=None, use_rescaled: bool=False):
    subjects = get_subjects(dataset)
    print("\nAll subjects found. Beginning MSM")
    print('*' * 50)
    for subject in subjects:
        time_points = get_subject_time_points(
            dataset, subject, alphanumeric_timepoints, time_point_number_start_character, starting_time)
        for i, time_point in enumerate(time_points):
            if i + 1 >= len(time_points):
                break
            younger_time = time_point
            older_time = time_points[i + 1]
            if younger_time != starting_time and older_time != starting_time:
                run_msm(dataset, output, subject, younger_time, older_time, "forward", younger_uses_mcribs, older_uses_mcribs, False, None,
                        levels, config, max_anat, max_cp, slurm_email, slurm_account, slurm_user, slurm_job_limit, use_rescaled)
                run_msm(dataset, output, subject, younger_time, older_time, "reverse", younger_uses_mcribs, older_uses_mcribs, False, None,
                        levels, config, max_anat, max_cp, slurm_email, slurm_account, slurm_user, slurm_job_limit, use_rescaled)


# Function to generate average maps
def generate_avg_maps(pre_msm_data: str, msm_data: str, subject: str, younger_timepoint: str, older_timepoint: str, max_cp: str | None=None, max_anat: str | None=None, younger_uses_mcribs: bool=False, older_uses_mcbribs: bool=False):
    # create output for average maps
    if max_cp == None:
        script_dir = path.dirname(path.realpath(__file__))
        max_cp = path.join(script_dir, "NeededFiles", "ico5sphere.LR.reg.surf.gii")
    if max_anat == None:
        script_dir = path.dirname(path.realpath(__file__))
        max_anat = path.join(script_dir, "NeededFiles", "ico6sphere.LR.reg.surf.gii")
        
    msm_avg_output = path.join(
        msm_data, f"{subject}_{younger_timepoint}_to_{older_timepoint}_avg")
    makedirs(msm_avg_output, exist_ok=True)

    # create variables for file locations from pre-msm
    if younger_uses_mcribs:
        younger_files = get_files_mcribs(pre_msm_data, subject, younger_timepoint)
    else:
        younger_files = get_files(pre_msm_data, subject, younger_timepoint)
    
    if older_uses_mcbribs:
        older_files = get_files_mcribs(pre_msm_data, subject, older_timepoint)
    else:
        older_files = get_files(pre_msm_data, subject, older_timepoint)
        
    left_younger_spherical_surface = younger_files[2]
    left_older_spherical_surface = older_files[2]
    right_younger_spherical_surface = younger_files[3]
    right_older_spherical_surface = older_files[3]

    # files for msm resverse registration
    msm_reverse_folder = path.join(
        msm_data, f"{subject}_{older_timepoint}_to_{younger_timepoint}")
    left_older_anatomical_surface_cpgrid = path.join(
        msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.LOAS.CPgrid.surf.gii")
    left_older_anatomical_surface_anatgrid = path.join(
        msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.LOAS.ANATgrid.surf.gii")
    left_base_sphere_reverse = path.join(
        msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.sphere.reg.surf.gii")
    left_cpgrid_sphere_reverse = path.join(
        msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.sphere.CPgrid.reg.surf.gii")
    left_anatgrid_sphere_reverse = path.join(
        msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.sphere.ANATgrid.reg.surf.gii")
    left_cpgrid_surfdist_reverse = path.join(
        msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.surfdist.CPgrid.func.gii")
    left_anatgrid_surfdist_reverse = path.join(
        msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.surfdist.ANATgrid.func.gii")
    right_older_anatomical_surface_cpgrid = path.join(
        msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.ROAS.CPgrid.surf.gii")
    right_older_anatomical_surface_anatgrid = path.join(
        msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.ROAS.ANATgrid.surf.gii")
    right_base_sphere_reverse = path.join(
        msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.sphere.reg.surf.gii")
    right_cpgrid_sphere_reverse = path.join(
        msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.sphere.CPgrid.reg.surf.gii")
    right_anatgrid_sphere_reverse = path.join(
        msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.sphere.ANATgrid.reg.surf.gii")
    right_cpgrid_surfdist_reverse = path.join(
        msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.surfdist.CPgrid.func.gii")
    right_anatgrid_surfdist_reverse = path.join(
        msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.surfdist.ANATgrid.func.gii")

    # files for msm forward registration
    msm_forward_folder = path.join(
        msm_data, f"{subject}_{younger_timepoint}_to_{older_timepoint}")
    left_base_sphere_forward = path.join(
        msm_forward_folder, f"{subject}_L_{younger_timepoint}-{older_timepoint}.sphere.reg.surf.gii")
    left_cpgrid_sphere_forward = path.join(
        msm_forward_folder, f"{subject}_L_{younger_timepoint}-{older_timepoint}.sphere.CPgrid.reg.surf.gii")
    left_anatgrid_sphere_forward = path.join(
        msm_forward_folder, f"{subject}_L_{younger_timepoint}-{older_timepoint}.sphere.ANATgrid.reg.surf.gii")
    left_cpgrid_surfdist_forward = path.join(
        msm_forward_folder, f"{subject}_L_{younger_timepoint}-{older_timepoint}.surfdist.CPgrid.func.gii")
    left_anatgrid_surfdist_forward = path.join(
        msm_forward_folder, f"{subject}_L_{younger_timepoint}-{older_timepoint}.surfdist.ANATgrid.func.gii")
    right_base_sphere_forward = path.join(
        msm_forward_folder, f"{subject}_R_{younger_timepoint}-{older_timepoint}.sphere.reg.surf.gii")
    right_cpgrid_sphere_forward = path.join(
        msm_forward_folder, f"{subject}_R_{younger_timepoint}-{older_timepoint}.sphere.CPgrid.reg.surf.gii")
    right_anatgrid_sphere_forward = path.join(
        msm_forward_folder, f"{subject}_R_{younger_timepoint}-{older_timepoint}.sphere.ANATgrid.reg.surf.gii")
    right_cpgrid_surfdist_forward = path.join(
        msm_forward_folder, f"{subject}_R_{younger_timepoint}-{older_timepoint}.surfdist.CPgrid.func.gii")
    right_anatgrid_surfdist_forward = path.join(
        msm_forward_folder, f"{subject}_R_{younger_timepoint}-{older_timepoint}.surfdist.ANATgrid.func.gii")

    # revfor sphere output names
    left_revfor_base_sphere = f"{msm_avg_output}/{subject}_L_{older_timepoint}-{younger_timepoint}.revfor.sphere.reg.surf.gii"
    right_revfor_base_sphere = f"{msm_avg_output}/{subject}_R_{older_timepoint}-{younger_timepoint}.revfor.sphere.reg.surf.gii"
    left_revfor_cpgrid_sphere = f"{msm_avg_output}/{subject}_L_{older_timepoint}-{younger_timepoint}.revfor.sphere.CPgrid.reg.surf.gii"
    right_revfor_cpgrid_sphere = f"{msm_avg_output}/{subject}_R_{older_timepoint}-{younger_timepoint}.revfor.sphere.CPgrid.reg.surf.gii"
    left_revfor_anatgrid_sphere = f"{msm_avg_output}/{subject}_L_{older_timepoint}-{younger_timepoint}.revfor.sphere.ANATgrid.reg.surf.gii"
    right_revfor_anatgrid_sphere = f"{msm_avg_output}/{subject}_R_{older_timepoint}-{younger_timepoint}.revfor.sphere.ANATgrid.reg.surf.gii"

    # avgfor sphere names
    left_avgfor_base_sphere = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.sphere.reg.surf.gii"
    right_avgfor_base_sphere = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.sphere.reg.surf.gii"
    left_avgfor_cpgrid_sphere = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.sphere.CPgrid.reg.surf.gii"
    right_avgfor_cpgrid_sphere = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.sphere.CPgrid.reg.surf.gii"
    left_avgfor_anatgrid_sphere = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.sphere.ANATgrid.reg.surf.gii"
    right_avgfor_anatgrid_sphere = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.sphere.ANATgrid.reg.surf.gii"

    # avgfor anat names
    left_avgfor_cpgrid_anat = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.anat.CPgrid.reg.surf.gii"
    right_avgfor_cpgrid_anat = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.anat.CPgrid.reg.surf.gii"
    left_avgfor_anatgrid_anat = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.anat.ANATgrid.reg.surf.gii"
    right_avgfor_anatgrid_anat = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.anat.ANATgrid.reg.surf.gii"

    # revfor surfdist names
    left_revfor_cpgrid_surfdist = f"{msm_avg_output}/{subject}_L_{older_timepoint}-{younger_timepoint}.revfor.surfdist.CPgrid.reg.func.gii"
    left_revfor_anatgrid_surfdist = f"{msm_avg_output}/{subject}_L_{older_timepoint}-{younger_timepoint}.revfor.surfdist.ANATgrid.reg.func.gii"
    right_revfor_cpgrid_surfdist = f"{msm_avg_output}/{subject}_R_{older_timepoint}-{younger_timepoint}.revfor.surfdist.CPgrid.reg.func.gii"
    right_revfor_anatgrid_surfdist = f"{msm_avg_output}/{subject}_R_{older_timepoint}-{younger_timepoint}.revfor.surfdist.ANATgrid.reg.func.gii"

    # angfor surfdist names
    left_avgfor_cpgrid_surfdist = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.surfdist.CPgrid.reg.func.gii"
    left_avgfor_anatgrid_surfdist = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.surfdist.ANATgrid.reg.func.gii"
    right_avgfor_cpgrid_surfdist = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.surfdist.CPgrid.reg.func.gii"
    right_avgfor_anatgrid_surfdist = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.surfdist.ANATgrid.reg.func.gii"

    # Generate Revfor spheres
    print("Begin generating revfor spheres")
    run(f"wb_command -surface-sphere-project-unproject {left_older_spherical_surface} {left_base_sphere_reverse} {left_younger_spherical_surface} {left_revfor_base_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-sphere-project-unproject {right_older_spherical_surface} {right_base_sphere_reverse} {right_younger_spherical_surface} {right_revfor_base_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-sphere-project-unproject {max_cp} {left_cpgrid_sphere_reverse} {max_cp} {left_revfor_cpgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-sphere-project-unproject {max_cp} {right_cpgrid_sphere_reverse} {max_cp} {right_revfor_cpgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-sphere-project-unproject {max_anat} {left_anatgrid_sphere_reverse} {max_anat} {left_revfor_anatgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-sphere-project-unproject {max_anat} {right_anatgrid_sphere_reverse} {max_anat} {right_revfor_anatgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)

    run(f"wb_command -surface-average {left_avgfor_base_sphere} -surf {left_base_sphere_forward} -surf {left_revfor_base_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-average {right_avgfor_base_sphere} -surf {right_base_sphere_forward} -surf {right_revfor_base_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-average {left_avgfor_cpgrid_sphere} -surf {left_cpgrid_sphere_forward} -surf {left_revfor_cpgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-average {right_avgfor_cpgrid_sphere} -surf {right_cpgrid_sphere_forward} -surf {right_revfor_cpgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-average {left_avgfor_anatgrid_sphere} -surf {left_anatgrid_sphere_forward} -surf {left_revfor_anatgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-average {right_avgfor_anatgrid_sphere} -surf {right_anatgrid_sphere_forward} -surf {right_revfor_anatgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)

    # Generate AvgFor Shpheres
    print("Begin generating avgfor spheres")
    run(f"wb_command -surface-modify-sphere -recenter {left_avgfor_base_sphere} 100 {left_avgfor_base_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-modify-sphere -recenter {right_avgfor_base_sphere} 100 {right_avgfor_base_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-modify-sphere -recenter {left_avgfor_cpgrid_sphere} 100 {left_avgfor_cpgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-modify-sphere -recenter {right_avgfor_cpgrid_sphere} 100 {right_avgfor_cpgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-modify-sphere -recenter {left_avgfor_anatgrid_sphere} 100 {left_avgfor_anatgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-modify-sphere -recenter {right_avgfor_anatgrid_sphere} 100 {right_avgfor_anatgrid_sphere}", shell=True, stdout=sys.stdout, stderr=sys.stderr)

    # Generate RevFor Anatomical Surfaces
    print("Begin generating revfor surfaces")
    run(f"wb_command -surface-resample {left_older_anatomical_surface_cpgrid} {max_cp} {left_avgfor_cpgrid_sphere} \"BARYCENTRIC\" {left_avgfor_cpgrid_anat}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-resample {right_older_anatomical_surface_cpgrid} {max_cp} {right_avgfor_cpgrid_sphere} \"BARYCENTRIC\" {right_avgfor_cpgrid_anat}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-resample {left_older_anatomical_surface_anatgrid} {max_anat} {left_avgfor_anatgrid_sphere} \"BARYCENTRIC\" {left_avgfor_anatgrid_anat}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-resample {right_older_anatomical_surface_anatgrid} {max_anat} {right_avgfor_anatgrid_sphere} \"BARYCENTRIC\" {right_avgfor_anatgrid_anat}", shell=True, stdout=sys.stdout, stderr=sys.stderr)

    # Generate revfor surfdist
    print("Begin generating revfor surfdist")
    # metric math *-1
    run(f"wb_command -metric-math 'X*-1' {left_revfor_cpgrid_surfdist} -var X {left_cpgrid_surfdist_reverse}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -metric-math 'X*-1' {left_revfor_anatgrid_surfdist} -var X {left_anatgrid_surfdist_reverse}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -metric-math 'X*-1' {right_revfor_cpgrid_surfdist} -var X {right_cpgrid_surfdist_reverse}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -metric-math 'X*-1' {right_revfor_anatgrid_surfdist} -var X {right_anatgrid_surfdist_reverse}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    
    """run(f"wb_command -metric-resample {left_cpgrid_surfdist_reverse} {left_cpgrid_sphere_reverse} {left_revfor_cpgrid_sphere} \"BARYCENTRIC\" {left_revfor_cpgrid_surfdist}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -metric-resample {left_anatgrid_surfdist_reverse} {left_anatgrid_sphere_reverse} {left_revfor_anatgrid_sphere} \"BARYCENTRIC\" {left_revfor_anatgrid_surfdist}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -metric-resample {right_cpgrid_surfdist_reverse} {right_cpgrid_sphere_reverse} {right_revfor_cpgrid_sphere} \"BARYCENTRIC\" {right_revfor_cpgrid_surfdist}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -metric-resample {right_anatgrid_surfdist_reverse} {right_anatgrid_sphere_reverse} {right_revfor_anatgrid_sphere} \"BARYCENTRIC\" {right_revfor_anatgrid_surfdist}", shell=True, stdout=sys.stdout, stderr=sys.stderr)"""

    # calculate average surfdist
    print("begin calculating avgfor surfdists")
    run(f"wb_command -metric-math '(J1+J2)/2' {left_avgfor_cpgrid_surfdist} -var J1 {left_revfor_cpgrid_surfdist} -var J2 {left_cpgrid_surfdist_forward}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -metric-math '(J1+J2)/2' {left_avgfor_anatgrid_surfdist} -var J1 {left_revfor_anatgrid_surfdist} -var J2 {left_anatgrid_surfdist_forward}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -metric-math '(J1+J2)/2' {right_avgfor_cpgrid_surfdist} -var J1 {right_revfor_cpgrid_surfdist} -var J2 {right_cpgrid_surfdist_forward}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -metric-math '(J1+J2)/2' {right_avgfor_anatgrid_surfdist} -var J1 {right_revfor_anatgrid_surfdist} -var J2 {right_anatgrid_surfdist_forward}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -set-structure {left_avgfor_cpgrid_surfdist} CORTEX_LEFT", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -set-structure {left_avgfor_anatgrid_surfdist} CORTEX_LEFT", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -set-structure {right_avgfor_cpgrid_surfdist} CORTEX_RIGHT", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -set-structure {right_avgfor_anatgrid_surfdist} CORTEX_RIGHT", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    print("complete\n")


# Function to run all average maps
def generate_avg_maps_all(ciftify_dataset: str, msm_dataset: str, max_cp: str | None=None, max_anat: str | None=None, starting_time: str | None=None, uses_mcribs: bool=False):
    print("\nBEGIN FUNCTION FOR AVG MAPS")
    print('*' * 50)
    
    if max_cp == None:
        script_dir = path.dirname(path.realpath(__file__))
        max_cp = path.join(script_dir, "NeededFiles", "ico5sphere.LR.reg.surf.gii")
    if max_anat == None:
        script_dir = path.dirname(path.realpath(__file__))
        max_anat = path.join(script_dir, "NeededFiles", "ico6sphere.LR.reg.surf.gii")
    
    for directory in listdir(msm_dataset):
        fields = directory.split("_")
        subject = fields[0]
        first_time = fields[1]
        second_time = fields[3]
        if first_time.isalpha():
            first_month = first_time
        else:
            first_month = int(sub("[^0-9]", "", first_time))
        
        if second_time.isalpha():
            second_month = second_time
        else:
            second_month = int(sub("[^0-9]", "", second_time))
        
        print(f"\nSubject: {subject}", f"First time pont and month: {first_time}/{first_month}",
              f"Second time point: {second_time}/{second_month}", sep="\n")
        if first_time == starting_time:
            continue
        elif second_time == starting_time:
            if uses_mcribs:
                print(f"Beginning average maps for {subject} for times {second_month} to {first_month} using mcribs")
                generate_avg_maps(ciftify_dataset, msm_dataset, subject, second_time, first_time, max_cp, max_anat, True, True)
            else:
                print(f"Beginning average maps for {subject} for times {second_month} to {first_month}")
                generate_avg_maps(ciftify_dataset, msm_dataset, subject, second_time, first_time, max_cp, max_anat)
        elif first_month < second_month:
            continue
        elif second_month < first_month:
            if uses_mcribs:
                print(f"Beginning average maps for {subject} for times {second_month} to {first_month} using mcribs")
                generate_avg_maps(ciftify_dataset, msm_dataset, subject, second_time, first_time, max_cp, max_anat, True, True)
            else:
                print(f"Beginning average maps for {subject} for times {second_month} to {first_month}")
                generate_avg_maps(ciftify_dataset, msm_dataset, subject, second_time, first_time, max_cp, max_anat)


# Rescale mcribs surface
def rescale_surfaces(dataset: str,  subject: str, time_point: str, uses_mcribs: bool=False):
    print(f"\nBEGIN RESCALING SURFACES FOR SUBJECT {subject} AT TIMEPOINT {time_point}")
    print('*' * 50)
    # Retrieve all necessay files
    print("Retriving subject files")
    if uses_mcribs:
        subject_files = get_files_mcribs(dataset, subject, time_point)
    else:
        subject_files = get_files(dataset, subject, time_point)
    left_midthickness_file = subject_files[0]
    right_midthickness_file = subject_files[1]
    subject_dir = subject_files[6]
    subject_full_name = subject_files[7]
    print(f"Subject directory: {subject_dir}")
    print(f"Subject full name: {subject_full_name}")
    print(f"Left midthickness file: {left_midthickness_file}")
    print(f"Right midthickness file: {right_midthickness_file}")
    # left_cortex = subject_files[8]
    # right_cortex = subject_files[9]
    
    # output file names
    left_shape_file = path.join(subject_dir, f"{subject_full_name}.L.areas.shape.gii")
    right_shape_file = path.join(subject_dir, f"{subject_full_name}.R.areas.shape.gii")
    left_affine_matrix = path.join(subject_dir, f"{subject_full_name}.L.rescaleaffine.nii")
    right_affine_matrix = path.join(subject_dir, f"{subject_full_name}.R.rescaleaffine.nii")
    left_rescaled_surface = path.join(subject_dir, f"{subject_full_name}.L.rescaled.surf.gii")
    right_rescaled_surface = path.join(subject_dir, f"{subject_full_name}.R.rescaled.surf.gii")
    
    # crete shape files
    print("Creating shape files")
    run(f"wb_command -surface-vertex-areas {left_midthickness_file} {left_shape_file}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-vertex-areas {left_midthickness_file} {right_shape_file}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    
    #subject cortex shape
    print("Calculating surface areas")
    run(f"wb_command -metric-stats {left_shape_file} -reduce SUM", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    command_output = run(f"wb_command -metric-stats {left_shape_file} -reduce SUM", shell=True, capture_output=True, text=True, check=True)
    left_surface_area = float(command_output.stdout.strip())
    
    run(f"wb_command -metric-stats {right_shape_file} -reduce SUM", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    command_output = run(f"wb_command -metric-stats {right_shape_file} -reduce SUM", shell=True, capture_output=True, text=True, check=True)
    right_surface_area = float(command_output.stdout.strip())
    print(f"Left Surface Area: {left_surface_area}")
    print(f"Right Surface Area: {right_surface_area}")
    
    # Rescale value calculations
    print("Calculating rescale values")
    left_rescale_value = sqrt(10000 / left_surface_area)
    right_rescale_value = sqrt(10000 / right_surface_area)
    print(f"Left Rescale Value: {left_rescale_value}")
    print(f"Right Rescale Value: {right_rescale_value}")
    
    # create affine matrix
    print("Creating affine matrices")
    with open(left_affine_matrix, "w+") as f:
        f.writelines([f"{left_rescale_value} 0 0 0\n",
                     f"0 {left_rescale_value} 0 0\n",
                     f"0 0 {left_rescale_value} 0\n",
                     "0 0 0 1"])
    
    with open(right_affine_matrix, "w+") as f:
        f.writelines([f"{right_rescale_value} 0 0 0\n",
                     f"0 {right_rescale_value} 0 0\n",
                     f"0 0 {right_rescale_value} 0\n",
                     "0 0 0 1"])
        
    # apply affine matrix
    print("Applying affine matrices to surfaces")
    run(f"wb_command -surface-apply-affine {left_midthickness_file} {left_affine_matrix} {left_rescaled_surface}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-apply-affine {right_midthickness_file} {right_affine_matrix} {right_rescaled_surface}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    print("Rescaling complete\n")


# Rescale surfaces for all subjects
def rescale_surfaces_all(dataset: str, uses_mcribs: bool=True):
    for subject_folder in listdir(dataset):
        subject_path = path.join(dataset, subject_folder)
        if path.isdir(subject_path):
            fields = subject_folder.split("_")
            subject = fields[1]
            time_point = fields[2]
            rescale_surfaces(dataset, subject, time_point, uses_mcribs)
            
            
# function to retrieve files for mcribs subject
def get_files_mcribs(dataset: str, subject: str, time_point: str):
    subject_dir = path.join(dataset, f"Subject_{subject}_{time_point}")
    # get all necessary files
    left_anatomical_surface = path.join(subject_dir, "lh.midthickness.surf.gii")
    right_anatomical_surface = path.join(subject_dir, "rh.midthickness.surf.gii")
    
    left_spherical_surface = path.join(subject_dir, "lh.sphere.reg2.surf.gii")
    right_spherical_surface = path.join(subject_dir, "rh.sphere.reg2.surf.gii")
    
    left_curvature = path.join(subject_dir, "lh.curv.shape.gii")
    right_curvature = path.join(subject_dir, "rh.curv.shape.gii")
    
    left_cortex = path.join(subject_dir, "lh.mean.thickness") # TODO Ffigure out what this should be
    right_cortex = path.join(subject_dir, "rh.mean.thickness") # TODO Ffigure out what this should be
    
    left_rescaled_surface = path.join(subject_dir, f"{subject}.L.rescaled.surf.gii")
    right_rescaled_surface = path.join(subject_dir, f"{subject}.R.rescaled.surf.gii")
    
    # return all files as list
    subject_files = [left_anatomical_surface, right_anatomical_surface,
                     left_spherical_surface, right_spherical_surface,
                     left_curvature, right_curvature,
                     subject_dir, subject,
                     left_cortex, right_cortex,
                     left_rescaled_surface, right_rescaled_surface]
    return subject_files    


# function to convert .curv files to .gii files
def convert_curvature(dataset: str, subject: str, time_point: str):
    subject_dir = path.join(dataset, f"Subject_{subject}_{time_point}")
    left_curv = path.join(subject_dir, "lh.curv")
    right_curv = path.join(subject_dir, "rh.curv")
    left_output = path.join(subject_dir, "lh.curv.shape.gii")
    right_output = path.join(subject_dir, "rh.curv.shape.gii")
    left_white_matter = path.join(subject_dir, "lh.white")
    right_white_matter = path.join(subject_dir, "rh.white")
    
    run(f"mris_convert -c {left_curv} {left_white_matter} {left_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"mris_convert -c {right_curv} {right_white_matter} {right_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    

# function for batch conversion of .curv files to .gii files
def convert_curvature_all(dataset: str):
    for subject_folder in listdir(dataset):
        subject_path = path.join(dataset, subject_folder)
        if path.isdir(subject_path):
            fields = subject_folder.split("_")
            subject = fields[1]
            time_point = fields[2]
            print(f"Converting curvature files for subject {subject} at time point {time_point}")
            convert_curvature(dataset, subject, time_point)
    print("Curvature conversion complete\n")    


# Function for concatenating registrations
def concatenate_registrations(msm_dataset: str, pre_msm_dataset: str, subject: str, concat_start_time: str, concat_end_time: str, resolution: str,
                             output: str, max_anat: str | None = None, max_cp: str | None = None, alphanumeric_timepoints: bool=False,
                             time_point_number_start_character: int | None=None, starting_time=None):
    print(f"Beginning concatenation for subject {subject} from {concat_start_time} to {concat_end_time}")
    # Gather default files
    script_dir = path.dirname(path.realpath(__file__))
    if max_anat == None:
        print("No max_anat provided, using default")
        max_anat = path.join(script_dir, "NeededFiles", "ico6sphere.LR.reg.surf.gii")
    if max_cp == None:
        print("No max_cp provided, using default")
        max_cp = path.join(script_dir, "NeededFiles", "ico5sphere.LR.reg.surf.gii")
    
    # Get all intermediate timepoints
    print(f"Finding intermediate time points")
    all_subject_timepoints = get_subject_time_points(pre_msm_dataset, subject, alphanumeric_timepoints, time_point_number_start_character, starting_time)
    starting_time_index = all_subject_timepoints.index(concat_start_time)
    if len(all_subject_timepoints) <= 2:
        print(f"Time points for subject only include start and end times, cannot concatenate")
        return
    intermediate_timepoints = all_subject_timepoints[starting_time_index + 1:]
    print(f"Found intermediate time points: {intermediate_timepoints}")
    
    # first concat run
    # Define directories
    forward_start_to_intermediate = path.join(msm_dataset, f"Subject_{subject}_{concat_start_time}_to_{intermediate_timepoints[0]}")
    avg_start_to_intermediate = path.join(msm_dataset, f"Subject_{subject}_{concat_start_time}_to_{intermediate_timepoints[0]}_avg")
    
    if len(intermediate_timepoints) > 1:
        print("Found multiple intermediate time points. Chain concatenation required.")
        # Used if there are multiple intermediate time points
        forward_intermediate_to_end = path.join(msm_dataset, f"Subject_{subject}_{intermediate_timepoints[0]}_to_{intermediate_timepoints[1]}")
        avg_intermediate_to_end = path.join(msm_dataset, f"Subject_{subject}_{intermediate_timepoints[0]}_to_{intermediate_timepoints[1]}_avg")
        concat_output_dir = path.join(output, f"Subject_{subject}_{concat_start_time}_to_{intermediate_timepoints[1]}_concat")
        left_concat_output = path.join(concat_output_dir, f"{subject}_L_{concat_start_time}-{intermediate_timepoints[1]}.concat.sphere.{resolution}.reg.surf.gii")
        right_concat_output = path.join(concat_output_dir, f"{subject}_R_{concat_start_time}-{intermediate_timepoints[1]}.concat.sphere.{resolution}.reg.surf.gii")
        left_as_time_end = path.join(forward_intermediate_to_end, f"{subject}_L_{intermediate_timepoints[0]}-{intermediate_timepoints[1]}.LOAS.{resolution}.surf.gii")
        right_as_time_end = path.join(forward_intermediate_to_end, f"{subject}_R_{intermediate_timepoints[0]}-{intermediate_timepoints[1]}.LOAS.{resolution}.surf.gii")
        left_anat_output = path.join(concat_output_dir, f"{subject}_L_{concat_start_time}-{intermediate_timepoints[1]}.concat.anat.{resolution}.reg.surf.gii")
        right_anat_output = path.join(concat_output_dir, f"{subject}_R_{concat_start_time}-{intermediate_timepoints[1]}.concat.anat.{resolution}.reg.surf.gii")
        left_surfdist_output = path.join(concat_output_dir, f"{subject}_L_{concat_start_time}-{intermediate_timepoints[1]}.concat.surfdist.{resolution}.func.gii")
        right_surfdist_output = path.join(concat_output_dir, f"{subject}_R_{concat_start_time}-{intermediate_timepoints[1]}.concat.surfdist.{resolution}.func.gii")
        left_sphere_unproject_from = path.join(avg_intermediate_to_end, f"{subject}_L_{intermediate_timepoints[0]}_{intermediate_timepoints[1]}.avgfor.sphere.{resolution}.reg.surf.gii")
        right_sphere_unproject_from = path.join(avg_intermediate_to_end, f"{subject}_R_{intermediate_timepoints[0]}_{intermediate_timepoints[1]}.avgfor.sphere.{resolution}.reg.surf.gii")
    else:
        print("Only one intermediate time point found. Single concatenation run.")
        # used if there is only one intermediate time point
        forward_intermediate_to_end = path.join(msm_dataset, f"Subject_{subject}_{intermediate_timepoints[0]}_to_{concat_end_time}")
        avg_intermediate_to_end = path.join(msm_dataset, f"Subject_{subject}_{intermediate_timepoints[0]}_to_{concat_end_time}_avg")
        concat_output_dir = path.join(output, f"Subject_{subject}_{concat_start_time}_to_{concat_end_time}_concat")
        left_concat_output = path.join(concat_output_dir, f"{subject}_L_{concat_start_time}-{concat_end_time}.concat.sphere.{resolution}.reg.surf.gii")
        right_concat_output = path.join(concat_output_dir, f"{subject}_R_{concat_start_time}-{concat_end_time}.concat.sphere.{resolution}.reg.surf.gii")
        left_as_time_end = path.join(forward_intermediate_to_end, f"{subject}_L_{intermediate_timepoints[0]}-{concat_end_time}.LOAS.{resolution}.surf.gii")
        right_as_time_end = path.join(forward_intermediate_to_end, f"{subject}_R_{intermediate_timepoints[0]}-{concat_end_time}.LOAS.{resolution}.surf.gii")
        left_anat_output = path.join(concat_output_dir, f"{subject}_L_{concat_start_time}-{concat_end_time}.concat.anat.{resolution}.reg.surf.gii")
        right_anat_output = path.join(concat_output_dir, f"{subject}_R_{concat_start_time}-{concat_end_time}.concat.anat.{resolution}.reg.surf.gii")
        left_surfdist_output = path.join(concat_output_dir, f"{subject}_L_{concat_start_time}-{concat_end_time}.concat.surfdist.{resolution}.func.gii")
        right_surfdist_output = path.join(concat_output_dir, f"{subject}_R_{concat_start_time}-{concat_end_time}.concat.surfdist.{resolution}.func.gii")
        left_sphere_unproject_from = path.join(avg_intermediate_to_end, f"{subject}_L_{intermediate_timepoints[0]}_{concat_end_time}.avgfor.sphere.{resolution}.reg.surf.gii")
        right_sphere_unproject_from = path.join(avg_intermediate_to_end, f"{subject}_R_{intermediate_timepoints[0]}_{concat_end_time}.avgfor.sphere.{resolution}.reg.surf.gii")
    
    left_sphere_in = path.join(avg_start_to_intermediate, f"{subject}_L_{concat_start_time}_{intermediate_timepoints[0]}.avgfor.sphere.{resolution}.reg.surf.gii")
    right_sphere_in = path.join(avg_start_to_intermediate, f"{subject}_R_{concat_start_time}_{intermediate_timepoints[0]}.avgfor.sphere.{resolution}.reg.surf.gii")
    left_surface_reference = path.join(forward_start_to_intermediate, f"{subject}_L_{concat_start_time}_{intermediate_timepoints[0]}.LYAS.{resolution}.surf.gii")
    right_surface_reference = path.join(forward_start_to_intermediate, f"{subject}_R_{concat_start_time}_{intermediate_timepoints[0]}.RYAS.{resolution}.surf.gii")
    
    if resolution == "CPgrid":
        sphere_project_to = max_cp
        spherical_surface = max_cp
    if resolution == "ANATgrid":
        sphere_project_to = max_anat
        spherical_surface = max_anat
    
    print(
        "Directories defined as\n"
        f"\tforward_start_to_intermediate: {forward_start_to_intermediate}\n"
        f"\tavg_start_to_intermediate: {avg_start_to_intermediate}\n"
        f"\tforward_intermediate_to_end: {forward_intermediate_to_end}\n"
        f"\tavg_intermediate_to_end: {avg_intermediate_to_end}\n"
        "\n"
        "Inputs\n"
        f"\tleft_sphere_in: {left_sphere_in}\n"
        f"\tright_sphere_in: {right_sphere_in}\n"
        f"\tsphere_project_to: {sphere_project_to}\n"
        f"\tleft_sphere_unproject_from: {left_sphere_unproject_from}\n"
        f"\tright_sphere_unproject_from: {right_sphere_unproject_from}\n"
        f"\tleft_as_time_end: {left_as_time_end}\n"
        f"\tright_as_time_end: {right_as_time_end}\n"
        f"\tspherical_surface: {spherical_surface}\n"
        f"\tleft_surface_reference: {left_surface_reference}\n"
        f"\tright_surface_reference: {right_surface_reference}\n"
        "\n"
        "Outputs\n"
        f"\tleft_concat_output: {left_concat_output}\n"
        f"\tright_concat_output: {right_concat_output}\n"
        f"\tleft_anat_output: {left_anat_output}\n"
        f"\tright_anat_output: {right_anat_output}\n"
        f"\tleft_surfdist_output: {left_surfdist_output}\n"
        f"\tright_surfdist_output: {right_surfdist_output}"
    )  
        
    # Run first set of commands
    print("Running commands")
    run(f"wb_command -surface-sphere-project-unproject {left_sphere_in} {sphere_project_to} {left_sphere_unproject_from} {left_concat_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-sphere-project-unproject {right_sphere_in} {sphere_project_to} {right_sphere_unproject_from} {right_concat_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    
    run(f"wb_command -surface-resample {left_as_time_end} {spherical_surface} {left_concat_output} 'BARYCENTRIC' {left_anat_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-resample {right_as_time_end} {spherical_surface} {right_concat_output} 'BARYCENTRIC' {right_anat_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    
    run(f"wb_command -surface-distortion {left_surface_reference} {left_anat_output} {left_surfdist_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    run(f"wb_command -surface-distortion {right_surface_reference} {right_anat_output} {right_surfdist_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
    print("Finished inital concatenation")
    
    if len(intermediate_timepoints) > 1:
        print("Chain concatenation starting")
        total_loops = len(intermediate_timepoints) - 2
        print(f"Total chains needed: {total_loops}")
        for i in range(1, len(intermediate_timepoints) - 1):
            print(f"Beginning chain concatenation {i}/{total_loops}")
            start_time = concat_start_time
            intermediate_time = intermediate_timepoints[i]
            end_time = intermediate_timepoints[i + 1]
            
            forward_start_to_intermediate = path.join(msm_dataset, f"Subject_{subject}_{start_time}_to_{intermediate_time}_concat")
            avg_start_to_intermediate = path.join(msm_dataset, f"Subject_{subject}_{start_time}_to_{intermediate_timepoints[0]}_avg")
            forward_intermediate_to_end = path.join(msm_dataset, f"Subject_{subject}_{intermediate_time}_to_{end_time}")
            avg_intermediate_to_end = path.join(msm_dataset, f"Subject_{subject}_{intermediate_time}_to_{end_time}_avg")
            
            concat_output_dir = path.join(output, f"Subject_{subject}_{start_time}_to_{end_time}_concat")
            left_concat_output = path.join(concat_output_dir, f"{subject}_L_{start_time}-{end_time}.concat.sphere.{resolution}.reg.surf.gii")
            right_concat_output = path.join(concat_output_dir, f"{subject}_R_{start_time}-{end_time}.concat.sphere.{resolution}.reg.surf.gii")
            left_anat_output = path.join(concat_output_dir, f"{subject}_L_{start_time}-{end_time}.concat.anat.{resolution}.reg.surf.gii")
            right_anat_output = path.join(concat_output_dir, f"{subject}_R_{start_time}-{end_time}.concat.anat.{resolution}.reg.surf.gii")
            left_surfdist_output = path.join(concat_output_dir, f"{subject}_L_{start_time}-{end_time}.concat.surfdist.{resolution}.func.gii")
            right_surfdist_output = path.join(concat_output_dir, f"{subject}_R_{start_time}-{end_time}.concat.surfdist.{resolution}.func.gii")
            
            left_sphere_in = path.join(concat_output_dir, f"{subject}_L_{start_time}-{intermediate_time}.concat.sphere.{resolution}.reg.surf.gii")
            right_sphere_in = path.join(concat_output_dir, f"{subject}_R_{start_time}-{intermediate_time}.concat.sphere.{resolution}.reg.surf.gii")
            left_surface_reference = path.join(concat_output_dir, f"{subject}_L_{start_time}-{intermediate_time}.concat.anat.{resolution}.reg.surf.gii")
            right_surface_reference = path.join(concat_output_dir, f"{subject}_R_{start_time}-{intermediate_time}.concat.anat.{resolution}.reg.surf.gii")
            
            left_as_time_end = path.join(forward_intermediate_to_end, f"{subject}_L_{intermediate_time}-{end_time}.LOAS.{resolution}.surf.gii")
            right_as_time_end = path.join(forward_intermediate_to_end, f"{subject}_R_{intermediate_time}-{end_time}.LOAS.{resolution}.surf.gii")
            left_sphere_unproject_from = path.join(avg_intermediate_to_end, f"{subject}_L_{intermediate_time}_{end_time}.avgfor.sphere.{resolution}.reg.surf.gii")
            right_sphere_unproject_from = path.join(avg_intermediate_to_end, f"{subject}_R_{intermediate_time}_{end_time}.avgfor.sphere.{resolution}.reg.surf.gii")

            print(
                "Directories defined as\n"
                f"\tforward_start_to_intermediate: {forward_start_to_intermediate}\n"
                f"\tavg_start_to_intermediate: {avg_start_to_intermediate}\n"
                f"\tforward_intermediate_to_end: {forward_intermediate_to_end}\n"
                f"\tavg_intermediate_to_end: {avg_intermediate_to_end}\n"
                "\n"
                "Inputs\n"
                f"\tleft_sphere_in: {left_sphere_in}\n"
                f"\tright_sphere_in: {right_sphere_in}\n"
                f"\tsphere_project_to: {sphere_project_to}\n"
                f"\tleft_sphere_unproject_from: {left_sphere_unproject_from}\n"
                f"\tright_sphere_unproject_from: {right_sphere_unproject_from}\n"
                f"\tleft_as_time_end: {left_as_time_end}\n"
                f"\tright_as_time_end: {right_as_time_end}\n"
                f"\tspherical_surface: {spherical_surface}\n"
                f"\tleft_surface_reference: {left_surface_reference}\n"
                f"\tright_surface_reference: {right_surface_reference}\n"
                "\n"
                "Outputs\n"
                f"\tleft_concat_output: {left_concat_output}\n"
                f"\tright_concat_output: {right_concat_output}\n"
                f"\tleft_anat_output: {left_anat_output}\n"
                f"\tright_anat_output: {right_anat_output}\n"
                f"\tleft_surfdist_output: {left_surfdist_output}\n"
                f"\tright_surfdist_output: {right_surfdist_output}"
            )
            
            print("Running commands")
            run(f"wb_command -surface-sphere-project-unproject {left_sphere_in} {sphere_project_to} {left_sphere_unproject_from} {left_concat_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
            run(f"wb_command -surface-sphere-project-unproject {right_sphere_in} {sphere_project_to} {right_sphere_unproject_from} {right_concat_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
            
            run(f"wb_command -surface-resample {left_as_time_end} {spherical_surface} {left_concat_output} 'BARYCENTRIC' {left_anat_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
            run(f"wb_command -surface-resample {right_as_time_end} {spherical_surface} {right_concat_output} 'BARYCENTRIC' {right_anat_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
            
            run(f"wb_command -surface-distortion {left_surface_reference} {left_anat_output} {left_surfdist_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
            run(f"wb_command -surface-distortion {right_surface_reference} {right_anat_output} {right_surfdist_output}", shell=True, stdout=sys.stdout, stderr=sys.stderr)
            print(f"Finished chain concatenation {i}/{total_loops}")
    
    print(f"Finished concatenation of subject {subject} form {concat_start_time} to {concat_end_time}")


# Command line interface
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MSM Pipeline Functions", usage="MSM_Pipeline.py [-h] <command> [<args>]")
    subparser = parser.add_subparsers(dest="command", required=True)
    
    # Get Ciftify Subject List
    csl = subparser.add_parser("get_ciftify_subject_list", help="Retrieve list of subejcts for Ciftify")
    csl.add_argument("--dataset", required=True, help="Path to data that needs to be ran through ciftify")
    csl.add_argument("--subjects", nargs='+', required=True, help="List of subject IDs space seperated")
    csl.add_argument("--pattern", required=True, help="Regex template of directory names using # as a stand-in for the subject ID. ie '.*_S_#_.*")

    # Is Slurm Queue Open
    sqo = subparser.add_parser("is_slurm_queue_open", help="Check how many open jobs are avaliable for the indicated user")
    sqo.add_argument("--slurm_user", required=True, help="The account name of the Slurm user to check")
    sqo.add_argument("--slurm_job_limit", required=False, type=int, default=500, help="The users Slurm job limit")

    # Run Ciftify
    rc = subparser.add_parser("run_ciftify", help="Run ciftify-recon-all on the indicated directories and palce them in the indicated output")
    rc.add_argument("--dataset", required=True, help="Path to data that needs to be ran through ciftify")
    rc.add_argument("--delimiter", required=True, help="Delimiiter used in directory names to seperate fields")
    rc.add_argument("--subject_index", required=True, type=int, help="Index of subject ID based on delimiter")
    rc.add_argument("--time_index", required=True, type=int, help="Index of time point based on delimeter")
    rc.add_argument("--output_path", required=True, help="Path to output of the command, must be empty")
    rc.add_argument("--slurm_account", required=False, help="Slurm account ID for submission")
    rc.add_argument("--slurm_user", required=False, help="Slurm username for checking queue")
    rc.add_argument("--slurm_email", required=False, help="Email for failed jobs to send to")
    rc.add_argument("--slurm_job_limit", required=False, type=int, help="The users Slurm job limit. Only needed if slurm job limit is not 500")
    rc.add_argument("--is_local", action="store_true", help="Use to make ciftify run in a local environment")

    # Get Subject Time Points
    gst = subparser.add_parser("get_subject_time_points", help="Retrieve list of time points based on subejct")
    gst.add_argument("--dataset", required=True, help="Path to directory containing subject data")
    gst.add_argument("--subject", required=True, help="The subject ID to retrieve time points for")
    gst.add_argument("--alphanumeric_timepoints", action="store_true", help="Use if the timepoints are alphanumeric")
    gst.add_argument("--time_point_number_start_character", required=False, type=int, help="The character where numbers begin in the timepoint 0 indexed, only required if using --alphanumeric_timepoints")
    gst.add_argument("--starting_time", required=False, help="Used if the starting time point uses a different naming convnetion")

    # Rescale Surfaces
    rs = subparser.add_parser("rescale_surfaces", help="Generates rescaled surfaces for the indicated subjeact and timepoint")
    rs.add_argument("--dataset", required=True, help="Path to directory containing subject data")
    rs.add_argument("--subject", required=True, help="The subject ID for rescale")
    rs.add_argument("--time_point", required=True, help="The time point to be rescaled")
    rs.add_argument("--uses_mcribs", action="store_true", help="Use if a dataset uses M-CRIB-S")
    
    # Rescale Surfaces All
    rsa = subparser.add_parser("rescale_surfaces_all", help="Rescale all subejcts in a given directory")
    rsa.add_argument("--dataset", required=True, help="Path to subjects to be rescaled")
    rsa.add_argument("--uses_mcribs", action="store_true", help="Include this flag if the full dataset uses M-CRIB-S")
    
    # Generate qc imagee
    gqi = subparser.add_parser("generate_qc_image", help="Generate qc scene and image for one subject")
    gqi.add_argument("--dataset", required=True, help="Path to directory containing MSM files for images you wish to create")
    gqi.add_argument("--subject", required=True, help="The subject ID for qc image creation")
    gqi.add_argument("--younger_timepoint", required=True, help="The younger time point for registration")
    gqi.add_argument("--older_timepoint", required=True, help="The older time point for registration")
    gqi.add_argument("--output", required=True, help="Location to place generated images")
    gqi.add_argument("--younger_uses_mcribs", action="store_true", help="Use if the younger time point uses M-CRIB-S")
    gqi.add_argument("--older_uses_mcribs", action="store_true", help="Use if the older time point uses M-CRIB-S")
    
    #qc all
    qa = subparser.add_parser("qc_all", help="Generate qc scene and image for all subjects in the indicated dataset")
    qa.add_argument("--dataset", required=True, help="Path to directory containing all MSM files for qc image creation")
    qa.add_argument("--output", required=True, help="Location to place generated images")
    qa.add_argument("--alphanumeric_timepoints", action="store_true", help="Use if the timepoints are alphanumeric")
    qa.add_argument("--time_point_number_start_character", required=False, type=int, help="The character where numbers begin in the timepoint 0 indexed, only required if using --alphanumeric_timepoints")
    qa.add_argument("--starting_time", required=False, help="Used if the starting time point uses a different naming convnetion")
    qa.add_argument("--uses_mcribs", action="store_true", help="Use if the dataset is mcribs")
    
    # Generate Post Processing Image
    gppi = subparser.add_parser("generate_post_processing_image", help="Generate post-processing scene and image for one subject")
    gppi.add_argument("--subject_directory", required=True, help="Path to directory containing MSM files for images you wish to create")
    gppi.add_argument("--resolution", choices=["CPgrid", "ANATgrid"], required=True, help="Resolution of registration for image creation, either CPgrid or ANATgrid")
    gppi.add_argument("--mode", choices=["forward", "reverse", "average"], required=True, help="Either forward or reverse dependant on registration")
    gppi.add_argument("--output", required=True, help="Location to copy the images to, will always place them in the subject directory as well")

    # Post Process All
    ppa = subparser.add_parser("post_process_all", help="Generatee Post Processing images for all MSM registrations")
    ppa.add_argument("--dataset", required=True, help="Loaction of MSM registrations")
    ppa.add_argument("--starting_time", required=True, help="Basline timepoint of data, used to determine if forward or reverse registration was used")
    ppa.add_argument("--resolution", choices=["CPgrid", "ANATgrid"], required=True, help="Resolution of registration for image creation, either CPgrid or ANATgrid")
    ppa.add_argument("--output", required=True, help="Location to copy the images to, will always place them in the subject directory as well")
    
    # Run MSM
    rm = subparser.add_parser("run_msm", help="Run MSM on the indicated subject and time points in the indicated direction")
    rm.add_argument("--dataset", required=True, help="Path to directory containing all time points for registration")
    rm.add_argument("--output", required=True, help="Path for output of MSM files, a folder for each registration will be created here")
    rm.add_argument("--subject", required=True, help="The subject ID MSM registration")
    rm.add_argument("--younger_timepoint", required=True, help="The younger time point for registration")
    rm.add_argument("--older_timepoint", required=True, help="The older time point for registration")
    rm.add_argument("--mode", choices=["forward", "reverse"], required=True, help="The registration mode, either forward or reverse")
    rm.add_argument("--is_local", action="store_true", help="Used to make MSM run in a local environment")
    rm.add_argument("--younger_uses_mcribs", action="store_true", help="Use to have MSM use mcribs naming conventions for younger timepoint")
    rm.add_argument("--older_uses_mcribs", action="store_true", help="Use to have MSM use mcribs naming conventions for older timepoint")
    rm.add_argument("--hemisphere", choices=["L", "R"], required=False, help="Specifiy hemisphere to run when using is_local. L or R only")
    rm.add_argument("--levels",required=False, type=int, default=6, help="Levels of MSM to run, see documentation for more information. Defaults to 6")
    rm.add_argument("--config", required=False, help="Path to MSM config file to use, see MSM documentation for more information. Only needed if not using default config")
    rm.add_argument("--max_anat", required=False, help="Path to MaxAnat reference sphere, typically ico6sphere. Only needed if not using default sphere")
    rm.add_argument("--max_cp", required=False, help="Path to MaxCP reference sphere, typically ico5sphere. Only needed if not using default sphere")
    rm.add_argument("--slurm_email", required=False, help="Email for failed jobs to send to. Only needed for remote jobs")
    rm.add_argument("--slurm_account", required=False, help="Slurm account ID for submission. Only needed for remote jobs")
    rm.add_argument("--slurm_user", required=False, help="Slurm username for checking queue. Only needed for remote jobs")
    rm.add_argument("--slurm_job_limit", required=False, help="The users Slurm job limit. Only needed for remote jobs, and if the slurm job limit is not 500")
    rm.add_argument("--use_rescaled", action="store_true", help="Include this flag if you wish to use rescaled surfaces for freesurfer subjects. M-CRIB-S subjects always use rescaled surfaces.")

    # Run MSM BL to All
    rmba = subparser.add_parser("run_msm_bl_to_all", help="Run MSM from baseline to all time points, both forward and reverse")
    rmba.add_argument("--dataset", required=True, help="Path to directory containing all data for registration")
    rmba.add_argument("--alphanumeric_timepoints", action="store_true", required=False, help="If the time points are alphanumeric")
    rmba.add_argument("--output", required=True, help="Path for output of MSM files, a folder for each registration will be created here")
    rmba.add_argument("--slurm_account", required=True, help="Slurm account ID for submission")
    rmba.add_argument("--slurm_user", required=True, help="Slurm username for checking queue")
    rmba.add_argument("--slurm_email", required=True, help="Email for failed jobs to send to")
    rmba.add_argument("--time_point_number_start_character", required=False, type=int, help="the character where numbers begin in the timepoint 0 indexed")
    rmba.add_argument("--starting_time", required=False, help="The time point used as baseline or 'bl' for all registrations")
    rmba.add_argument("--younger_uses_mcribs", action="store_true", help="Use to have MSM use mcribs naming conventions for younger timepoint")
    rmba.add_argument("--older_uses_mcribs", action="store_true", help="Use to have MSM use mcribs naming conventions for older timepoint")
    rmba.add_argument("--slurm_job_limit", required=False, help="The users Slurm job limit. Only needed if the slurm job limit is not 500")
    rmba.add_argument("--levels",required=False, type=int, default=6, help="Levels of MSM to run, see documentation for more information, defaults to 6")
    rmba.add_argument("--config", required=False, help="Path to MSM config file to use, see MSM documentation for more information. Only needed if not using default config")
    rmba.add_argument("--max_anat", required=False, help="Path to MaxAnat reference sphere, typically ico6sphere. Only needed if not using default sphere")
    rmba.add_argument("--max_cp", required=False, help="Path to MaxCP reference sphere, typically ico5sphere. Only needed if not using default sphere")
    rmba.add_argument("--use_rescaled", action="store_true", help="Include this flag if you wish to use rescaled surfaces for freesurfer subjects. M-CRIB-S subjects always use rescaled surfaces.")

    # Run MSM Short Time Windows
    rmst = subparser.add_parser("run_msm_short_time_windows", help="Run MSM on sequential time points, both forward and reverse")
    rmst.add_argument("--dataset", required=True, help="Path to directory containing all data for registration")
    rmst.add_argument("--output", required=True, help="Path for output of MSM files, a folder for each registration will be created here")
    rmst.add_argument("--slurm_account", required=True, help="Slurm account ID for submission")
    rmst.add_argument("--slurm_user", required=True, help="Slurm username for checking queue")
    rmst.add_argument("--slurm_email", required=True, help="Email for failed jobs to send to")
    rmst.add_argument("--alphanumeric_timepoints", action="store_true", required=False, help="If the time points are alphanumeric")
    rmst.add_argument("--time_point_number_start_character", required=False, type=int, help="the character where numbers begin in the timepoint 0 indexed")
    rmst.add_argument("--younger_uses_mcribs", action="store_true", help="Use to have MSM use mcribs naming conventions for younger timepoint")
    rmst.add_argument("--older_uses_mcribs", action="store_true", help="Use to have MSM use mcribs naming conventions for older timepoint")
    rmst.add_argument("--slurm_job_limit", required=False, help="The users Slurm job limit. Only needed if slurm job limit is not 500")
    rmst.add_argument("--levels",required=False, type=int, default=6, help="Levels of MSM to run, see documentation for more information, defaults to 6")
    rmst.add_argument("--config", required=False, help="Path to MSM config file to use, see MSM documentation for more information. Only needed if not using default config")
    rmst.add_argument("--max_anat", required=False, help="Path to MaxAnat reference sphere, typically ico6sphere. Only needed if not using default sphere")
    rmst.add_argument("--max_cp", required=False, help="Path to MaxCP reference sphere, typically ico5sphere. Only needed if not using default sphere")
    rmst.add_argument("--starting_time", required=False, help="The starting time point. Only used if you want to skip baseline registrations")
    rmst.add_argument("--use_rescaled", action="store_true", help="Include this flag if you wish to use rescaled surfaces for freesurfer subjects. M-CRIB-S subjects always use rescaled surfaces.")
    
    # Generate Avg Maps
    gam = subparser.add_parser("generate_avg_maps", help="Generate average maps for one subject")
    gam.add_argument("--ciftify_dataset", required=True, help="Path to data from ciftify run")
    gam.add_argument("--msm_dataset", required=True, help="Path to MSM registrations")
    gam.add_argument("--subject", required=True, help="Subject ID to generate average maps")
    gam.add_argument("--younger_timepoint", required=True, help="The younger time point of the registration")
    gam.add_argument("--older_timepoint", required=True, help="The older time point of the registration")
    gam.add_argument("--max_cp", required=False, help="Path to MaxCP reference sphere, typically ico5sphere")
    gam.add_argument("--max_anat", required=False, help="Path to MaxANAT reference sphere, typically ico6sphere")
    gam.add_argument("--younger_uses_mcribs", action="store_true", help="Use if the younger time point is from an mcribs dataset")
    gam.add_argument("--older_uses_mcribs", action="store_true", help="Use if the older time point is from an mcribs dataset")
        
    # Generate All Avg Maps
    raa = subparser.add_parser("generate_avg_maps_all", help="Run average map generation on all subjects")
    raa.add_argument("--ciftify_dataset", required=True, help="Path to data from ciftify run")
    raa.add_argument("--msm_dataset", required=True, help="Path to MSM registrations")
    raa.add_argument("--max_cp", required=False, help="Path to MaxCP reference sphere, typically ico5sphere")
    raa.add_argument("--max_anat", required=False, help="Path to MaxANAT reference sphere, typically ico6sphere")
    raa.add_argument("--starting_time", required=False, help="Basleine of registrations, used to determine which avg maps are needed")
    raa.add_argument("--uses_mcribs", action="store_true", help="Use if the dataset is from mcribs. Note that both time points are assumed to use mcribs when this flag is used. Mcribs to freesurfer average maps can not be batch generated.")

    # Convert curvature
    cc = subparser.add_parser("convert_curvature", help="Convert .curv files to .gii files for one subject and time point from a mcribs dataset")
    cc.add_argument("--dataset", required=True, help="Path to directory containing subject data")
    cc.add_argument("--subject", required=True, help="The subject ID to retrieve files for")
    cc.add_argument("--time_point", required=True, help="The time point to retrieve files for")
    
    # Convert curvature all
    cca = subparser.add_parser("convert_curvature_all", help="Convert .curv files to .gii files for all subjects and time points in a mcribs dataset")
    cca.add_argument("--dataset", required=True, help="Path to directory containing all subject data")
    
    # Concat Registrations
    cr = subparser.add_parser("concatenate_registrations", help="Concatenate MSM registrations together, used to help eliminate noise in registrations across longer time points")
    cr.add_argument("--msm_dataset", required=True, help="Path to directory containing MSM registrations; folder should contain directories for each each time point needed")
    cr.add_argument("--pre_msm_dataset", required=True, help="Path to to either the ciftify output or M-CRIB-S data")
    cr.add_argument("--subject", required=True, help="Subject ID to concatenate registrations for")
    cr.add_argument("--concat_start_time", required=True, help="The starting time point for the concatenation, most likely the same as the starting time point of the first registration in the chain")
    cr.add_argument("--concat_end_time", required=True, help="The ending time point for the concatenation, most likely the same as the ending time point of the last registration in the chain")
    cr.add_argument("--resolution", choices=["CPgrid", "ANATgrid"], required=True, help="Resolution of registration for concatenation, either CPgrid or ANATgrid")
    cr.add_argument("--output", required=True, help="Path for output of concatenated registrations, a folder for each concatenation will be created here")
    cr.add_argument("--max_anat", required=False, help="Path to MaxAnat reference sphere, typically ico6sphere. Only needed if not using default sphere")
    cr.add_argument("--max_cp", required=False, help="Path to MaxCP reference sphere, typically ico5sphere. Only needed if not using default sphere")
    cr.add_argument("--alphanumeric_timepoints", action="store_true", help="Use if the time points are alphanumeric, will sort time points based on the numbers in the time point name, so make sure those are consistent across time points")
    cr.add_argument("--time_point_number_start_character", required=False, type=int, help="The character where numbers begin in the timepoint 0 indexed, only required if using --alphanumeric_timepoints")
    cr.add_argument("--starting_time", required=False, help="Used if the starting time point uses a different naming convnetion")
    
    args = parser.parse_args()
    
    if args.command == "get_ciftify_subject_list":
        args_dict = vars(args)
        args_dict.pop("command", None)
        get_ciftify_subject_list(**args_dict)
    elif args.command == "is_slurm_queue_open":
        args_dict = vars(args)
        args_dict.pop("command", None)
        is_slurm_queue_open(**args_dict)
    elif args.command == "run_ciftify":
        args_dict = vars(args)
        args_dict.pop("command", None)
        run_ciftify(**args_dict)
    elif args.command == "get_subject_time_points":
        args_dict = vars(args)
        args_dict.pop("command", None)
        get_subject_time_points(**args_dict)
    elif args.command == "rescale_surfaces":
        args_dict = vars(args)
        args_dict.pop("command", None)
        rescale_surfaces(**args_dict)
    elif args.command == "rescale_surfaces_all":
        args_dict = vars(args)
        args_dict.pop("command", None)
        rescale_surfaces_all(**args_dict)
    elif args.command == "generate_qc_image":
        args_dict = vars(args)
        args_dict.pop("command", None)
        generate_qc_image(**args_dict)
    elif args.command == "qc_all":
        args_dict = vars(args)
        args_dict.pop("command", None)
        qc_all(**args_dict)
    elif args.command == "generate_post_processing_image":
        args_dict = vars(args)
        args_dict.pop("command", None)
        generate_post_processing_image(**args_dict)
    elif args.command == "run_msm":
        args_dict = vars(args)
        args_dict.pop("command", None)
        run_msm(**args_dict)
    elif args.command == "run_msm_bl_to_all":
        args_dict = vars(args)
        args_dict.pop("command", None)
        run_msm_bl_to_all(**args_dict)
    elif args.command == "run_msm_short_time_windows":
        args_dict = vars(args)
        args_dict.pop("command", None)
        run_msm_short_time_windows(**args_dict)
    elif args.command == "post_process_all":
        args_dict = vars(args)
        args_dict.pop("command", None)
        post_process_all(**args_dict)
    elif args.command == "generate_avg_maps":
        args_dict = vars(args)
        args_dict.pop("command", None)
        generate_avg_maps(**args_dict)
    elif args.command == "generate_avg_maps_all":
        args_dict = vars(args)
        args_dict.pop("command", None)
        generate_avg_maps_all(**args_dict)
    elif args.command == "convert_curvature":
        args_dict = vars(args)
        args_dict.pop("command", None)
        convert_curvature(**args_dict)
    elif args.command == "convert_curvature_all":
        args_dict = vars(args)
        args_dict.pop("command", None)
        convert_curvature_all(**args_dict)
    elif args.command == "concatenate_registrations":
        args_dict = vars(args)
        args_dict.pop("command", None)
        concatenate_registrations(**args_dict)
