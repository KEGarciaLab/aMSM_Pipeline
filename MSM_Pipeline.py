#!/usr/bin/env python3.11

import argparse
import sys
from os import listdir, path, makedirs, remove, walk
from re import compile, sub
from subprocess import check_output, Popen, PIPE, STDOUT, run
from time import sleep
from string import Template
from typing import Literal
from shutil import copy2
from datetime import datetime
from math import sqrt
from fnmatch import fnmatch
from sys import exit



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


log_path = path.expanduser(f'~/Scripts/MyScripts/logs/MSM_Pipeline/full_pipeline_log-{datetime.now().strftime("%Y-%m-%d_%H:%M:%S")}.txt')
makedirs(path.dirname(log_path), exist_ok=True)
log_file = open(log_path, 'w+')
sys.stdout = Tee(sys.__stdout__, log_file)
sys.stderr = Tee(sys.__stderr__, log_file)
Mode = Literal["forward", "reverse", "average"]
Hemisphere = Literal["L", "R"]
PIPELINE_VERSION = '1.5.3-indev'

print(f"{datetime.now()}[START] Begin pipeline execution")
print(f"{datetime.now()}[INFO] Pipeline Version: {PIPELINE_VERSION}")
# makes sure all commands log properly
def run_logged(cmd, step=None):
    header = f"[RUN]" if not step else f"[RUN:{step}]"
    print(f"\n{datetime.now()}{header} {cmd}\n")

    with open(log_path, "a") as log_file:
        process = Popen(cmd, shell=True, stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)

        for line in process.stdout:
            print(line, end="")          # live console output
            log_file.write(line)         # append to log file
            log_file.flush()             # ensure immediate write
        process.wait()

    if process.returncode != 0:
        print(f"{datetime.now()}[ERROR] Command failed with return code {process.returncode}")

    return process


# prints error messages
def fail(msg):
    print(f"{datetime.now()}[ERROR] {msg}")
    print(f"{datetime.now()}[ERROR] Exiting pipeline. If you feel this is a bug please report at https://github.com/KEGarciaLab/aMSM_Pipeline/issues")
    print(f"{datetime.now()}[ERROR] Full log can be found at {log_path}")
    exit(1)


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
    # ---------------------------------
    # Check slurm queue against limit
    # ---------------------------------
    print(f"\n{datetime.now()}[SLURM QUEUE CHECK] Checking slurm queue for {slurm_user} with job limit of {slurm_job_limit}")
    
    print(f"{datetime.now()}[STEP] Creating output folder")
    user_home = path.expanduser('~')
    output_dir = rf"{user_home}/Scripts/MyScripts/Output/MSM_Pipeline"
    makedirs(output_dir, exist_ok=True)
    
    print(f"{datetime.now()}[STEP] Running squeue and capturing output")
    jobs = check_output(["squeue", f"-u{slurm_user}", "-o '%.10i %.9p %40j %.8u %.10T %.10M %.6D %R'", "-a"]).decode("utf-8")
    
    print(f"{datetime.now()}[STEP] Writing current queue to text file")
    with open(rf"{user_home}/Scripts/MyScripts/Output/MSM_Pipeline/queue.txt", 'w+') as f:
        f.write(jobs)
    
    print(f"{datetime.now()}[STEP] Counting jobs in queue")
    with open(rf"{user_home}/Scripts/MyScripts/Output/MSM_Pipeline/queue.txt", 'r') as f:
        jobs = (sum(1 for line in f)) - 1
    print(f"{datetime.now()}[INFO] Current jobs in queue: {jobs}")
    open_jobs = slurm_job_limit - jobs
    print(f"{datetime.now()}[INFO] Number of jobs open: {open_jobs}")
    print(f"{datetime.now()}[COMPLETE] Finished checking queue. Returning number of open jobs as int.")
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
            run_logged(fr"bash {temp_output}/Subject_{subject}_{time_point}_recon_all.sh")
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
            run_logged(fr"sbatch {temp_output}/Subject_{subject}_{time_point}_recon_all.sh")
        
        remove(fr"{temp_output}/Subject_{subject}_{time_point}_recon_all.sh")


# Helper function for sorting time points
def sort_time_points(time_points: list, number_start_character: int, starting_time=None):
    print(f"\n{datetime.now()}[SORT TIME POINTS] Starting custom alphanumeric sort function")
    print(f"{datetime.now()}[INFO] Time point list to sort:")
    print("\n".join(f"    {time_point}" for time_point in time_points))
    
    # --------------------------------------------------
    # Creating copy of list and removing starting time
    # --------------------------------------------------
    copy = time_points.copy()
    print(f"{datetime.now()}[INFO] Crated copy of orginal list")
    if starting_time is not None and starting_time in time_points:
        print(f"{datetime.now()}[INFO] Starting time located in list removing from copy for sorting")
        copy.pop(time_points.index(starting_time))

    # --------------------------------
    # Sorting based on number start
    # --------------------------------
    print(f"{datetime.now()}[INFO] sorting by number which starts at character index {number_start_character}")
    copy.sort(key=lambda time_point: int(
        time_point[number_start_character:]))

    # ---------------------
    # Readd starting time
    # ---------------------
    if starting_time is not None and starting_time in time_points:
        print(f"{datetime.now()}[INFO] Insterting starting time {starting_time} to the beginning of list")
        copy.insert(0, starting_time)
    print(f"{datetime.now()}[INFO] Sorted time points:")
    print("\n".join(f"    {time_point}" for time_point in copy))
    print(f"{datetime.now()}[COMPLETE] Finished sorting time points, returning sorted list")
    return copy


# Function to get all time points for a subject
def get_subject_time_points(dataset: str, subject: str, alphanumeric_timepoints: bool=False, time_point_number_start_character: int | None=None, starting_time=None):
    print(f"\n{datetime.now()}[GET TIME POINTS] Getting time points for subject {subject} with these options:")
    print(f"    Dataset: {dataset}")
    print(f"    Alphanumeric Timepoints: {alphanumeric_timepoints}")
    print(f"    Time Point Number Start Character: {time_point_number_start_character}")
    print(f"    Starting Time: {starting_time}")
    # -----------------------------
    # Searching for Subject Dirs
    # -----------------------------
    subject_dirs = []
    print(f"{datetime.now()}[STEP] Locating all subject directories")
    pattern = compile(fr"Subject_{subject}_.*")
    print(f"{datetime.now()}[INFO] Searching for subject dirs matching Subject_{subject}_.*")
    for entry in listdir(dataset):
        full_path = path.join(dataset, entry)
        if path.isdir(full_path) and pattern.match(entry):
            print(f"{datetime.now()}[INFO] Found Match: {entry}")
            print(f"{datetime.now()}[INFO] Adding to subject_dirs list")
            subject_dirs.append(entry)
    
    print(f"{datetime.now()}[FLIES] Found the following directories:")
    print("\n".join(f"    {dir}" for dir in subject_dirs))

    # --------------------------
    # Extracting Time Points
    #---------------------------
    print(f"{datetime.now()}[STEP] Extracting timepoints from directory names")
    time_points = []
    for directory in subject_dirs:
        print(f"{datetime.now()}[INFO] Current directory: {directory}")
        fields = directory.split("_")
        time_point = fields[2]
        if time_point not in time_points:
            print(f"{datetime.now()}[INFO] Found time point: {time_point}")
            print(f"{datetime.now()}[INFO] Adding to time points list")
            time_points.append(time_point)
    print(f"{datetime.now()}[INFO] Found the following time points:")
    print("\n".join(f"    {time_point}" for time_point in time_points))

    # ----------------------
    # Sorting Time Points
    # ----------------------
    if alphanumeric_timepoints:
        print(f"{datetime.now()}[INFO] Using alphanumeric time points, using custom sort")
        print(f"{datetime.now()}[FUNCTION] sort_time_points(time_points=time_points, number_start_character=time_point_number_start_character, starting_time=starting_time)")
        time_points = sort_time_points(time_points=time_points, number_start_character=time_point_number_start_character, starting_time=starting_time)
        print()
    elif time_points[0].isdigit():
        print(f"{datetime.now()}[INFO] Numeric time points detected, using interger sort")
        time_points.sort(key=int)
    else:
        print(f"{datetime.now()}[INFO] Using lexicograpic sort")
        time_points.sort()
    
    print(f"{datetime.now()}[INFO] Sorted time points:")
    print("\n".join(f"    {time_point}" for time_point in time_points))
    print(f"{datetime.now()}[COMPLETE] Retrieved all time points for subject {subject}")
    return time_points


# Helper function for searching files
def find(patterns, search_path, required_dirs=None):
    if isinstance(patterns, str):
        patterns = [patterns]

    print(f'\n{datetime.now()}[FIND] Finding file matching patterns {patterns} starting at {search_path}')

    for pattern in patterns:
        print(f"{datetime.now()}[INFO] Trying pattern: {pattern}")

        for root, dirs, files in walk(search_path):
            print(f"{datetime.now()}[INFO] Searching in directory: {root}")

            if required_dirs:
                parts = path.normpath(root).split(path.sep)
                if not all(directory in parts for directory in required_dirs):
                    continue

            for name in files:
                if fnmatch(name, pattern):
                    full_path = path.join(root, name)
                    print(f"{datetime.now()}[INFO] Found file matching pattern: {name}")
                    print(f"{datetime.now()}[INFO] Full path is: {full_path}")
                    print(f"{datetime.now()}[COMPLETE] Found file. Returning file path object.")
                    return full_path

    fail(f"No file found matching any pattern in {search_path}")            


# Helper function for retriving MSM files
def get_files(dataset: str, subject: str, time_point: str, is_rescaled=False):
    print(f"\n{datetime.now()}[GET FILES] Getting files for Subject {subject} at time point {time_point} in dataset {dataset}")
    
    # -------------------------
    # Set up variables
    # -------------------------
    print(f"{datetime.now()}[STEP] Locating subject directory and subejct prefix")
    subject_dir = path.join(dataset, f"Subject_{subject}_{time_point}")
    subdirs = [directory for directory in listdir(subject_dir) if path.isdir(
        path.join(subject_dir, directory)) and directory != "zz_templates"]
    if not subdirs:
        return
    subject_dir = path.join(subject_dir, subdirs[0])
    subject_full_name = subdirs[0]
    print(f"{datetime.now()}[INFO] Subject directory located at {subject_dir}")
    print(f"{datetime.now()}[INFO] Subejct prefix: {subject_full_name}")
    
    # ---------------------------------------------
    # Locate files
    # ---------------------------------------------
    print(f"{datetime.now()}[STEP] Locating Files")
    print(f'{datetime.now()}[FUNCTION] find(patterns="*.L.midthickness.32k_fs_LR.surf.gii", search_path=subject_dir, required_dirs=["T1w"])')
    left_anatomical_surface = find(patterns="*.L.midthickness.32k_fs_LR.surf.gii", search_path=subject_dir, required_dirs=["T1w"])
    print()
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="*.R.midthickness.32k_fs_LR.surf.gii", search_path=subject_dir, required_dirs=["T1w"])')
    right_anatomical_surface = find(patterns="*.R.midthickness.32k_fs_LR.surf.gii", search_path=subject_dir, required_dirs=["T1w"])
    print()
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="*.L.sphere.32k_fs_LR.surf.gii", search_path=subject_dir, required_dirs=["T1w"])')
    left_spherical_surface = find(patterns="*.L.sphere.32k_fs_LR.surf.gii", search_path=subject_dir, required_dirs=["T1w"])
    print()
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="*.R.sphere.32k_fs_LR.surf.gii", search_path=subject_dir, required_dirs=["T1w"])')
    right_spherical_surface = find(patterns="*.R.sphere.32k_fs_LR.surf.gii", search_path=subject_dir, required_dirs=["T1w"])
    print()
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="*.L.atlasroi.32k_fs_LR.shape.gii", search_path=subject_dir)')
    left_cortex = find(patterns="*.L.atlasroi.32k_fs_LR.shape.gii", search_path=subject_dir)
    print()
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="*.R.atlasroi.32k_fs_LR.shape.gii", search_path=subject_dir)')
    right_cortex = find(patterns="*.R.atlasroi.32k_fs_LR.shape.gii", search_path=subject_dir)
    print()
    
    
    print(f"{datetime.now()}[FILES] Located the following files:")
    print(f"    LAS: {left_anatomical_surface}")
    print(f"    RAS: {right_anatomical_surface}")
    print(f"    LSS: {left_spherical_surface}")
    print(f"    RSS: {right_spherical_surface}")
    print(f"    LEFT CORTEX: {left_cortex}")
    print(f"    RIGHT CORTEX: {right_cortex}")
    

    # --------------------------------------------------------
    # Locate curvature file
    # --------------------------------------------------------
    print(f"{datetime.now()}[STEP] locate curvature file")
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="*.curvature.32k_fs_LR.dscalar.nii", search_path=subject_dir)')
    base_curvature = find(patterns="*.curvature.32k_fs_LR.dscalar.nii", search_path=subject_dir)
    print()
    
    print(f"{datetime.now()}[FILES] Located the following files:")
    print(f"    BASE CURVATURE: {base_curvature}")
    
    # ----------------------------------------
    # Seperate curvature
    # ----------------------------------------
    print(f"{datetime.now()}[STEP] Define outputs and directory")
    subject_curvature_dir = path.dirname(base_curvature)
    left_curvature = fr"{subject_curvature_dir}/{subject_full_name}_Curvature.L.func.gii"
    right_curvature = fr"{subject_curvature_dir}/{subject_full_name}_Curvature.R.func.gii"
    
    print(f"{datetime.now()}[INFO] Curvature Directory: {subject_curvature_dir}")
    print(f"{datetime.now()}[INFO] Left Curvature Output: {left_curvature}")
    print(f"{datetime.now()}[INFO] Right Curvature Output: {right_curvature}")
    run_logged(fr"wb_command -cifti-separate {base_curvature} COLUMN -metric CORTEX_LEFT {left_curvature} -metric CORTEX_RIGHT {right_curvature}", step="SEP CURV")

    # ---------------------------------------------
    # Grab rescaled and resampled files if needed
    #----------------------------------------------
    if is_rescaled:
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.L.rescaled.surf.gii", search_path=subject_dir)')
        left_rescaled_surface = find(patterns="*.L.rescaled.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.R.rescaled.surf.gii", search_path=subject_dir)')
        right_rescaled_surface = find(patterns="*.R.rescaled.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.L.generated.sphere.surf.gii", search_path=subject_dir)')
        left_generated_sphere = find(patterns="*.L.generated.sphere.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.R.generated.sphere.surf.gii", search_path=subject_dir)')
        right_generated_sphere = find(patterns="*.R.generated.sphere.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.L.rescaled.ANATgrid.surf.gii", search_path=subject_dir)')
        left_resampled_anatgrid=find(patterns="*.L.rescaled.ANATgrid.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.L.rescaled.CPgrid.surf.gii", search_path=subject_dir)')
        left_resampled_cpgrid=find(patterns="*.L.rescaled.CPgrid.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.L=R.rescaled.ANATgrid.surf.gii", search_path=subject_dir)')
        right_resampled_anatgrid=find(patterns="*.R.rescaled.ANATgrid.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.R.rescaled.CPgrid.surf.gii", search_path=subject_dir)')
        right_resampled_cpgrid=find(patterns="*.R.rescaled.CPgrid.surf.gii", search_path=subject_dir)
        print()
    else:
        left_rescaled_surface = right_rescaled_surface = left_generated_sphere = right_generated_sphere = left_resampled_anatgrid = right_resampled_anatgrid = left_resampled_cpgrid = right_resampled_cpgrid = None
    
    # -----------------------
    # Return Files
    # -----------------------
    subject_files = {
        "LAS": left_anatomical_surface,
        "RAS": right_anatomical_surface,
        "LSS": left_spherical_surface,
        "RSS": right_spherical_surface,
        "LEFT CURVATURE": left_curvature,
        "RIGHT CURVATURE": right_curvature,
        "SUBJECT DIR": subject_dir,
        "SUBJECT PREFIX": subject_full_name,
        "LEFT CORTEX": left_cortex,
        "RIGHT CORTEX": right_cortex,
        "LEFT RESCALE": left_rescaled_surface,
        "RIGHT RESCALE": right_rescaled_surface,
        "LEFT RESCALE ANAT": left_resampled_anatgrid,
        "LEFT RESCALE CP": left_resampled_cpgrid,
        "RIGHT RESCALE ANAT": right_resampled_anatgrid,
        "RIGHT RESCALE CP": right_resampled_cpgrid,
        "LEFT GEN SPHERE": left_generated_sphere,
        "RIGHT GEN SPHERE": right_generated_sphere,
    }
    
    print(f"{datetime.now()}[INFO] Returning the following:")
    for k,v in subject_files.items():
        print(f"    {k}: {v}")
    
    print(f"{datetime.now()}[COMPELTE] Finished finding files for Subject {subject} at time point {time_point} in {dataset}. Returning dictonary of files")
    return subject_files


# Generate pre-MSM qc image
def generate_qc_image(dataset: str, subject: str, younger_timepoint: str, older_timepoint: str, output: str, younger_uses_mcribs: bool=False, older_uses_mcribs: bool=False):
    
    print(f"\n{datetime.now()}[QC] Generating QC image for subject={subject} ({younger_timepoint} → {older_timepoint})\n")
    # -------------------------
    # Locate surfaces
    # -------------------------
    print(f"{datetime.now()}[STEP] Locating surfaces")

    if younger_uses_mcribs and older_uses_mcribs:
        print(f"{datetime.now()}[INFO] Both timepoints use MCRIBS pipeline")
        print(f"{datetime.now()}[FUNCTION] get_files_mcribs(dataset=dataset, subject=subject, time_point=younger_timepoint, is_rescaled=True)")
        younger_files = get_files_mcribs(dataset=dataset, subject=subject, time_point=younger_timepoint, is_rescaled=True)
        print()
        print(f"{datetime.now()}[FUNCTION] get_files_mcribs(dataset=dataset, subject=subject, time_point=older_timepoint, is_rescaled=True)")
        older_files = get_files_mcribs(dataset=dataset, subject=subject, time_point=older_timepoint, is_rescaled=True)
        print()
    elif younger_uses_mcribs and not older_uses_mcribs:
        print(f"{datetime.now()}[INFO] Younger timepoint uses MCRIBS pipeline")
        print(f"{datetime.now()}[FUNCTION] get_files_mcribs(dataset=dataset, subject=subject, time_point=younger_timepoint, is_rescaled=True)")
        younger_files = get_files_mcribs(dataset=dataset, subject=subject, time_point=younger_timepoint, is_rescaled=True)
        print()
        print(f"{datetime.now()}[FUNCTION] get_files(dataset=dataset, subject=subject, time_point=older_timepoint, is_rescaled=True)")
        older_files = get_files(dataset=dataset, subject=subject, time_point=older_timepoint, is_rescaled=True)
        print()
    elif not younger_uses_mcribs and older_uses_mcribs:
        print(f"{datetime.now()}[INFO] Older timepoint uses MCRIBS pipeline")
        print(f"{datetime.now()}[FUNCTION] get_files(dataset=dataset, subject=subject, time_point=younger_timepoint, is_rescaled=True)")
        younger_files = get_files(dataset=dataset, subject=subject, time_point=younger_timepoint, is_rescaled=True)
        print()
        print(f"{datetime.now()}[FUNCTION] get_files_mcribs(dataset=dataset, subject=subject, time_point=older_timepoint, is_rescaled=True)")
        older_files = get_files_mcribs(dataset=dataset, subject=subject, time_point=older_timepoint, is_rescaled=True)
        print()
    else:
        print(f"{datetime.now()}[FUNCTION] get_files(dataset=dataset, subject=subject, time_point=younger_timepoint)")
        younger_files = get_files(dataset=dataset, subject=subject, time_point=younger_timepoint)
        print()
        print(f"{datetime.now()}[FUNCTION] get_files(dataset=dataset, subject=subject, time_point=older_timepoint)")
        older_files = get_files(dataset=dataset, subject=subject, time_point=older_timepoint)
        print()

    if younger_uses_mcribs or older_uses_mcribs:
        left_younger_surface = younger_files["LEFT RESCALE ANAT"]
        right_younger_surface = younger_files["RIGHT RESCALE ANAT"]
        left_older_surface = older_files["LEFT RESCALE ANAT"]
        right_older_surface = older_files["RIGHT RESCALE ANAT"]
    else:
        left_younger_surface = younger_files["LAS"]
        right_younger_surface = younger_files["RAS"]
        left_older_surface = older_files["LAS"]
        right_older_surface = older_files["RAS"]

    print(f"{datetime.now()}[FILES] Selected surfaces:")
    print(f"    Younger L: {left_younger_surface}")
    print(f"    Younger R: {right_younger_surface}")
    print(f"    Older   L: {left_older_surface}")
    print(f"    Older   R: {right_older_surface}")

    # -------------------------
    # Create spec file
    # -------------------------
    print("\n[STEP] Creating spec file")

    spec_file = path.join(output, f"{subject}_{younger_timepoint}_to_{older_timepoint}.spec")
    print(f"{datetime.now()}[INFO] Spec file: {spec_file}")

    run_logged(f"wb_command -add-to-spec-file {spec_file} CORTEX_LEFT {left_younger_surface}", step="SPEC")
    run_logged(f"wb_command -add-to-spec-file {spec_file} CORTEX_LEFT {left_older_surface}", step="SPEC")
    run_logged(f"wb_command -add-to-spec-file {spec_file} CORTEX_RIGHT {right_younger_surface}", step="SPEC")
    run_logged(f"wb_command -add-to-spec-file {spec_file} CORTEX_RIGHT {right_older_surface}", step="SPEC")

    # -------------------------
    # Create scene file
    # -------------------------
    print("\n[STEP] Creating scene file")

    script_dir = path.dirname(path.realpath(__file__))
    template_path = path.join(script_dir, "Templates", "pre_msm_qc_template.scene")

    print(f"{datetime.now()}[INFO] Using template: {template_path}")

    with open(template_path, "r") as f:
        template = Template(f.read())

    scene_file = path.join(output, f"{subject}_{younger_timepoint}_to_{older_timepoint}.scene")

    print(f"{datetime.now()}[INFO] Writing scene file: {scene_file}")

    with open(scene_file, "w+") as f:
        f.write(template.substitute(
            left_younger_surface=left_younger_surface,
            left_older_surface=left_older_surface,
            right_younger_surface=right_younger_surface,
            right_older_surface=right_older_surface
        ))

    print("\n[STEP] Generating QC image")

    image_file = path.join(output, f"{subject}_{younger_timepoint}_to_{older_timepoint}.png")
    print(f"{datetime.now()}[INFO] Output image: {image_file}")

    run_logged(f"wb_command -show-scene {scene_file} 1 {image_file} 1024 512",step="RENDER")
    print(f"{datetime.now()}[COMPLETE] FInished generating qc images")

    
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
    print(f"\n{datetime.now()}[POST PROCESSING] Starting post processing")
    
    # ---------------------
    # Extracting metadata
    # ---------------------
    print(f"{datetime.now()}[STEP] Gathering registration info")
    subject_basename = path.basename(subject_directory)
    subject_basename_list = subject_basename.split("_")
    subject = subject_basename_list[0]
    starting_time = subject_basename_list[1]
    ending_time = subject_basename_list[3]
    print("")
    
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
    run_logged(f"wb_command -metric-palette {left_surface_map} MODE_AUTO_SCALE -palette-name raich6_clrmid")
    run_logged(f"wb_command -metric-palette {right_surface_map} MODE_AUTO_SCALE -palette-name raich6_clrmid")

    # add to spec file
    print("Adding to Spec File")
    run_logged(f"wb_command -add-to-spec-file {spec_file} CORTEX_LEFT {left_younger_surface}")
    run_logged(f"wb_command -add-to-spec-file {spec_file} CORTEX_LEFT {left_older_surface}")
    run_logged(f"wb_command -add-to-spec-file {spec_file} CORTEX_LEFT {left_surface_map}")
    run_logged(f"wb_command -add-to-spec-file {spec_file} CORTEX_RIGHT {right_younger_surface}")
    run_logged(f"wb_command -add-to-spec-file {spec_file} CORTEX_RIGHT {right_older_surface}")
    run_logged(f"wb_command -add-to-spec-file {spec_file} CORTEX_RIGHT {right_surface_map}")

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
        
    run_logged(f"wb_command -show-scene {scene_auto_scale} 1 {image_auto_scale} 1024 512")
    run_logged(f"wb_command -show-scene {scene_set_scale} 1 {image_set_scale} 1024 512")

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

        if first_month.isdigit() and second_month.isdigit():
            if int(first_month) < int(second_month):
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
        
        else:
            if first_month < second_month:
                print("Mode: Forward")
                generate_post_processing_image(full_path,
                                            resolution,
                                            "forward",
                                            subject_output)

            elif first_month > second_month:
                print("Mode: Reverse")
                generate_post_processing_image(full_path,
                                            resolution,
                                            "reverse",
                                            subject_output)


# helper function for retriving subjects
def get_subjects(dataset: str):
    # ----------------------
    # Get Subjects Dataset
    # ----------------------
    print(f"\n{datetime.now()}[GET SUBJECTS] Getting subjects from dataset {dataset}")
    subjects = []
    for directory in listdir(dataset):
        full_path = path.join(dataset, directory)
        if path.isdir(full_path):
            fields = directory.split("_")
            subject = fields[1]
            if subject not in subjects:
                print(f"{datetime.now()}[INFO] Found subject {subject} at {full_path} adding to subjects list")
                subjects.append(subject)
    subjects.sort()
    print(f"{datetime.now()}[Info] Found the following subjects")
    for subject in subjects:
        print(f"    {subject}")
    print(f"{datetime.now()}[COMPLETE] Found all subjects in dataset {dataset}. Returning list of subjects")
    return subjects


# Helper function for sphere generation
def generate_sphere(subject_dir, subject_prefix, left_midthickness, right_midthickness, max_anat):
    # --------------------------------------------
    # Generate sphere based on rescaled surfaces
    # --------------------------------------------
    print(f"\n{datetime.now()}[GENERATE SPHERE] Generating sphere for rescaled surface")
    print(f"{datetime.now()}[INFO] USing the following settings:")
    print(f"    LEFT MIDTHICKNESS: {left_midthickness}")
    print(f"    RIGHT MIDTHICKNESS: {right_midthickness}")
    print(f"    MAX ANAT: max_anat")
    
    # ---------------------
    # Set up outputs
    # ---------------------
    print(f"{datetime.now()}[INFO] Defining output files")
    left_smoothed = path.join(subject_dir, "lh.midthickness.smoothed.surf.gii")
    right_smoothed = path.join(subject_dir, "rh.midthickness.smoothed.surf.gii")
    
    left_inflated = path.join(subject_dir, "lh.inflated.surf.gii")
    right_inflated = path.join(subject_dir, "rh.inflated.surf.gii")
    
    left_matched = path.join(subject_dir, "lh.matched.surf.gii")
    right_matched = path.join(subject_dir, "rh.matched.surf.gii")
    
    left_spherical_surface = path.join(subject_dir, f"{subject_prefix}.L.generated.sphere.surf.gii")
    right_spherical_surface = path.join(subject_dir, f"{subject_prefix}.R.generated.sphere.surf.gii")
    
    print(f"{datetime.now()}[FILES] Files will be gnereaterd as follows:")
    print(f"    LEFT SMOOTHED: {left_smoothed}")
    print(f"    RIGHT SMOOTHED: {right_smoothed}")
    print(f"    LEFT INFLATED: {left_inflated}")
    print(f"    RIGHT INFLATED: {right_inflated}")
    print(f"    LEFT MATCHED: {left_matched}")
    print(f"    RIGHT MATCHED: {right_matched}")
    
    # ----------------------------
    # SMOOTHING MIDTHICKNESS
    # ----------------------------
    print(f"{datetime.now()}[STEP] Smoothing midthickness")
    run_logged(f'wb_command -surface-smoothing {left_midthickness} 1 10000 {left_smoothed}', step="SMOOTHING")
    run_logged(f'wb_command -surface-smoothing {right_midthickness} 1 10000 {right_smoothed}', step="SMOOTHING")
    
    # ---------------------------
    # INFLATE SMOOTHED SURFACE
    # ---------------------------
    print(f"{datetime.now()}[STEP] Inflating smoothed surfaces")
    run_logged(f'wb_command -surface-inflation {left_smoothed} {left_smoothed} 10 1 100 2 {left_inflated}', step="INFLATE")
    run_logged(f'wb_command -surface-inflation {right_smoothed} {right_smoothed} 10 1 100 2 {right_inflated}', step="INFLATE")
    
    # -------------------------------------
    # MATCH INFLATED SURFACE TO ICOSPHERE
    # -------------------------------------
    print(f"{datetime.now()}[STEP] Matching inflated surface to icosphere")
    run_logged(f'wb_command -surface-match {max_anat} {left_inflated} {left_matched}', step="MATCHING")
    run_logged(f'wb_command -surface-match {max_anat} {right_inflated} {right_matched}', step="MATCHING")
    
    # ------------------
    # CENTERING SPHERE
    # ------------------
    print(f"{datetime.now()}[INFO] Centering matched sphere")
    run_logged(f'wb_command -surface-modify-sphere -recenter {left_matched} 100 {left_spherical_surface}', step="CENTERING")
    run_logged(f'wb_command -surface-modify-sphere -recenter {right_matched} 100 {right_spherical_surface}', step="CENTERING")
    
    # ---------------
    # RETURN FILES
    # ---------------
    print(f"{datetime.now()}[INFO] Returning path objects for left and right spherical surface")
    print(f"{datetime.now()}[COMPLETE] Finished generating shperes in {subject_dir}")
    return left_spherical_surface, right_spherical_surface


# Helper Function for template replacement
def generate_from_template(template_path, output_path, template_dict):
    print(f"\n{datetime.now()}[TEMPLATE] Generating script at {output_path} from template located at {template_path}")
    print(f"{datetime.now()}[STEP] Reading template")
    with open(template_path, "r") as f:
        template_read = f.read()
    template = Template(template_read)
    try:
        print(f"{datetime.now()}[INFO] Values to write:")
        for k,v in template_dict.items():
                print(f"    {k}: {v}")
        print(f"{datetime.now()}[STEP] Attempting Substitution")
        to_write = template.substitute(template_dict)
    except:
        fail("Unable to substitue template. Check log to ensure all files were gathered correctly")
    with open(output_path, "w+") as f:
        print(f"{datetime.now()}[INFO] Writng substituded template to {output_path}")
        f.write(to_write)
    print(f"{datetime.now()}[COMPLETE] Finished generating script from template")


# Function for running MSM commands
def run_msm(dataset: str, output: str, subject: str, younger_timepoint: str,
            older_timepoint: str, mode: Mode, younger_uses_mcribs: bool=False, older_uses_mcribs: bool=False,
            is_local: bool=False, hemisphere: Hemisphere | None=None, levels: int=6, config: str | None=None, 
            max_anat: str | None=None, max_cp: str | None=None, slurm_email: str | None=None, slurm_account: str | None=None,
            slurm_user: str | None=None, slurm_job_limit: int | None=None, use_rescaled: bool=False):
    
    print(f"\n{datetime.now()}[MSM] Starting MSM run for subject {subject} from time point {younger_timepoint} to {older_timepoint} in {mode} mode")
    for name, value in locals().items():
        print(f"    {name}: {value}")

    # -------------------------------------
    # Setting up defaults and variables
    # -------------------------------------
    print(f"{datetime.now()}[STEP] Seting up options and variables")
    user_home = path.expanduser('~')
    script_dir = path.dirname(path.realpath(__file__))
    if config == None:
        print(f"{datetime.now()}[INFO] No config file provided, using default")
        config = path.join(script_dir, "NeededFiles", "configAnatGrid6")
    if max_anat == None:
        print(f"{datetime.now()}[INFO] max_anat not provided, using default")
        max_anat = path.join(script_dir, "NeededFiles", "ico6sphere.LR.reg.surf.gii")
    if max_cp == None:
        print(f"{datetime.now()}[INFO] max_cp not provided, using default")
        max_cp = path.join(script_dir, "NeededFiles", "ico5sphere.LR.reg.surf.gii")
    if is_local and hemisphere is None:
        fail("local mode selected but no hemisphere seleceted")
    if mode != "forward" and mode != "reverse":
        fail("mode must be forward or reverse")
        
    
    print(f"{datetime.now()}[INFO] Mode is {mode}, setting script path to match")
    if mode == "forward":
        temp_output = path.join(user_home, "Scripts", "MyScripts", "Output", "MSM_Pipeline", "MSM_scripts", fr"{subject}_{younger_timepoint}_to_{older_timepoint}")
    elif mode == "reverse":
        temp_output = path.join(user_home, "Scripts", "MyScripts", "Output", "MSM_Pipeline", "MSM_scripts", fr"{subject}_{older_timepoint}_to_{younger_timepoint}")
    makedirs(temp_output, exist_ok=True)
    
    print(f"{datetime.now()}[INFO] The following settings will be used:")
    print(f"    Subject: {subject}")
    print(f"    Younger Time Point: {younger_timepoint}")
    print(f"    Older Time Point: {older_timepoint}")
    print(f"    Mode: {mode}")
    print(f"    Local: {is_local}")
    print(f"    Hemisphere: {Hemisphere}")
    print(f"    User Home: {user_home}")
    print(f"    Config File: {config}")
    print(f"    Max CP: {max_cp}")
    print(f"    Max Anat: {max_anat}")
    print(f"    Genreated Script Dir: {temp_output}")

    # -------------------------
    # Retrieve Younger Files
    # -------------------------
    print(f"{datetime.now()}[STEP] Retrieving files for younger timepoint")
    if younger_uses_mcribs:
        print(f"{datetime.now()}[INFO] Younger time point uses M-CRIB-S naming conventions")
        print(f"{datetime.now()}[FUNCTION] get_files_mcribs(dataset=dataset, subject=subject, time_point=younger_timepoint, is_rescaled=True)")
        younger_files = get_files_mcribs(dataset=dataset, subject=subject, time_point=younger_timepoint, is_rescaled=True)
        print()
        
        print(f"{datetime.now()}[INFO] M-CRIB-S Surfaces must be rescaled. Using rescaled surfaces")
        left_younger_anatomical_surface = younger_files["LEFT RESCALE"]
        right_younger_anatomical_surface = younger_files["RIGHT RESCALE"]
        left_younger_spherical_surface = younger_files["LEFT GEN SPHERE"]
        right_younger_spherical_surface = younger_files["RIGHT GEN SPHERE"]
    else:
        print(f"{datetime.now()}[INFO] Younger timepoint uses Ciftify/Freesurfer naming conventiions")
        if use_rescaled:
            print(f"{datetime.now()}[INFO] Rescale option is set to true for Freesurfer subejcts")
            print(f"{datetime.now()}[FUNCTION] get_files(dataset=dataset, subject=subject, time_point=younger_timepoint, is_rescaled=True)")
            younger_files = get_files(dataset=dataset, subject=subject, time_point=younger_timepoint, is_rescaled=True)
            print()
            left_younger_anatomical_surface = younger_files["LEFT RESCALE"]
            right_younger_anatomical_surface = younger_files["RIGHT RESCALE"]
            left_younger_spherical_surface = younger_files["LEFT GEN SPHERE"]
            right_younger_spherical_surface = younger_files["RIGHT GEN SPHERE"]
            
        else:
            print(f"{datetime.now()}[INFO] Rescale option set to False for Freesurfer subjects")
            print(f"{datetime.now()}[FUNCTION] get_files(dataset=dataset, subject=subject, time_point=younger_timepoint)")
            younger_files = get_files(dataset=dataset, subject=subject, time_point=younger_timepoint)
            print()
            left_younger_anatomical_surface = younger_files["LAS"]
            right_younger_anatomical_surface = younger_files["RAS"]
            left_younger_spherical_surface = younger_files["LSS"]
            right_younger_spherical_surface = younger_files["RSS"]
    
    left_younger_curvature = younger_files["LEFT CURVATURE"]
    right_younger_curvature = younger_files["RIGHT CURVATURE"]
    print(f"{datetime.now()}[FILES] Younger files retrieved")
    print(f"    LYAS: {left_younger_anatomical_surface}")
    print(f"    RYAS: {right_younger_anatomical_surface}")
    print(f"    LYSS: {left_younger_spherical_surface}")
    print(f"    RYSS: {right_younger_spherical_surface}")
    print(f"    LYC: {left_younger_curvature}")
    print(f"    RYC: {right_younger_curvature}")
    
    # -------------------------
    # Retrieve Older Files
    # -------------------------    
    print(f"{datetime.now()}[STEP] Retrieving files for older timepoint")    
    if older_uses_mcribs:
        print(f"{datetime.now()}[INFO] Older time point uses M-CRIB-S naming conventions")
        print(f"{datetime.now()}[FUNCTION] get_files_mcribs(dataset=dataset, subject=subject, time_point=older_timepoint, is_rescaled=True)")
        older_files = get_files_mcribs(dataset=dataset, subject=subject, time_point=older_timepoint, is_rescaled=True)
        print()
        
        print(f"{datetime.now()}[INFO] M-CRIB-S Surfaces must be rescaled. Using rescaled surfaces")
        left_older_anatomical_surface = older_files["LEFT RESCALE"]
        right_older_anatomical_surface = older_files["RIGHT RESCALE"]
        left_older_spherical_surface = older_files["LEFT GEN SPHERE"]
        right_older_spherical_surface = older_files["RIGHT GEN SPHERE"]
    else:
        print(f"{datetime.now()}[INFO] Older timepoint uses Ciftify/Freesurfer naming conventiions")
        if use_rescaled:
            print(f"{datetime.now()}[INFO] Rescale option is set to true for Freesurfer subjects")
            print(f"{datetime.now()}[FUNCTION] get_files(dataset=dataset, subject=subject, time_point=older_timepoint, is_rescaled=True)")
            older_files = get_files(dataset=dataset, subject=subject, time_point=older_timepoint, is_rescaled=True)
            print()
            left_older_anatomical_surface = older_files["LEFT RESCALE"]
            right_older_anatomical_surface = older_files["RIGHT RESCALE"]
            left_older_spherical_surface = older_files["LEFT GEN SPHERE"]
            right_older_spherical_surface = older_files["RIGHT GEN SPHERE"]
        else:
            print(f"{datetime.now()}[INFO] Rescale option set to False for Freesurfer subjects")
            print(f"{datetime.now()}[FUNCTION] get_files(dataset=dataset, subject=subject, time_point=older_timepoint)")
            older_files = get_files(dataset=dataset, subject=subject, time_point=older_timepoint)
            print()
            left_older_anatomical_surface = older_files["LAS"]
            right_older_anatomical_surface = older_files["RAS"]
            left_older_spherical_surface = older_files["LSS"]
            right_older_spherical_surface = older_files["RSS"]

    left_older_curvature = older_files["LEFT CURVATURE"]
    right_older_curvature = older_files["RIGHT CURVATURE"]
    print(f"{datetime.now()}[FILES] Older files retrieved")
    print(f"    LOAS: {left_older_anatomical_surface}")
    print(f"    ROAS: {right_older_anatomical_surface}")
    print(f"    LOSS: {left_older_spherical_surface}")
    print(f"    ROSS: {right_older_spherical_surface}")
    print(f"    LOC: {left_older_curvature}")
    print(f"    ROC: {right_older_curvature}")

    #--------------------
    # Generate Scritps
    #--------------------
    print(f"{datetime.now()}[STEP] Generating scripts for MSM runs")
    script_dir = path.dirname(path.realpath(__file__))
    template_dir = path.join(script_dir, "Templates")
    print(f"{datetime.now()}[INFO] Templates located in {template_dir}")
    if mode == "forward":
        # ---------------------
        # Set up forward info
        # ---------------------
        print(f"{datetime.now()}[INFO] Mode is set to forward, creating output directories and files")
        output = path.join(output, fr"{subject}_{younger_timepoint}_to_{older_timepoint}")
        temp_output = path.join(user_home, "Scripts", "MyScripts", "Output", "MSM_Pipeline", "MSM_scripts", fr"{subject}_{younger_timepoint}_to_{older_timepoint}")
        makedirs(output, exist_ok=True)
        makedirs(temp_output, exist_ok=True)
        print(f"{datetime.now()}[INFO] Output directory created at {output}")
        print(f"{datetime.now()}[INFO] Script directory created at {temp_output}")
        
        left_file_prefix = fr"{output}/{subject}_L_{younger_timepoint}-{older_timepoint}."
        right_file_prefix = fr"{output}/{subject}_R_{younger_timepoint}-{older_timepoint}."
        script_output_l = path.join(temp_output, f"Subject_{subject}_L_{younger_timepoint}-{older_timepoint}_MSM.sh")
        script_output_r = path.join(temp_output, f"Subject_{subject}_R_{younger_timepoint}-{older_timepoint}_MSM.sh")
        
        if is_local:
            print(f"{datetime.now()}[INFO] Local flag used. Using local run templates")
            template_path_l = path.join(template_dir, "MSM_template_forward_L_local.txt")
            template_path_r = path.join(template_dir, "MSM_template_forward_R_local.txt")
            template_dict_l = {
                "levels": levels,
                "config": config,
                "yss": left_younger_spherical_surface,
                "oss": left_older_spherical_surface,
                "yc": left_younger_curvature,
                "oc": left_older_curvature,
                "yas": left_younger_anatomical_surface,
                "oas": left_older_anatomical_surface,
                "f_out": left_file_prefix,
                "maxanat": max_anat,
                "maxcp": max_cp
            }
            template_dict_r = {
                "levels": levels,
                "config": config,
                "yss": right_younger_spherical_surface,
                "oss": right_older_spherical_surface,
                "yc": right_younger_curvature,
                "oc": right_older_curvature,
                "yas": right_younger_anatomical_surface,
                "oas": right_older_anatomical_surface,
                "f_out": right_file_prefix,
                "maxanat": max_anat,
                "maxcp": max_cp
            }
            
            
        else:
            print(f"{datetime.now()}[INFO] Local flag not used, using remote templates")
            template_path_l = path.join(template_dir, "MSM_template_forward_L.txt")
            template_path_r = path.join(template_dir, "MSM_template_forward_R.txt")
            template_dict_l = {
                "subject": subject,
                "starting_time": younger_timepoint,
                "ending_time": older_timepoint,
                "user_home": user_home,
                "email": slurm_email,
                "account": slurm_account,
                "levels": levels,
                "config": config,
                "yss": left_younger_spherical_surface,
                "oss": left_older_spherical_surface,
                "yc": left_younger_curvature,
                "oc": left_older_curvature,
                "yas": left_younger_anatomical_surface,
                "oas": left_older_anatomical_surface,
                "f_out": left_file_prefix,
                "maxanat": max_anat,
                "maxcp": max_cp
            }
            template_dict_r = {
                "subject": subject,
                "starting_time": younger_timepoint,
                "ending_time": older_timepoint,
                "user_home": user_home,
                "email": slurm_email,
                "account": slurm_account,
                "levels": levels,
                "config": config,
                "yss": right_younger_spherical_surface,
                "oss": right_older_spherical_surface,
                "yc": right_younger_curvature,
                "oc": right_older_curvature,
                "yas": right_younger_anatomical_surface,
                "oas": right_older_anatomical_surface,
                "f_out": right_file_prefix,
                "maxanat": max_anat,
                "maxcp": max_cp
            }
    
    elif mode == "reverse":
        # ---------------------
        # Set up reverse info
        # ---------------------
        print(f"{datetime.now()}[INFO] Mode is set to reverse, creating output directories and files")
        output = path.join(output, fr"{subject}_{older_timepoint}_to_{younger_timepoint}")
        temp_output = path.join(user_home, "Scripts", "MyScripts", "Output", "MSM_Pipeline", "MSM_scripts", fr"{subject}_{older_timepoint}_to_{younger_timepoint}")
        makedirs(output, exist_ok=True)
        makedirs(temp_output, exist_ok=True)
        print(f"{datetime.now()}[INFO] Output directory created at {output}")
        print(f"{datetime.now()}[INFO] Script directory created at {temp_output}")
        
        left_file_prefix = fr"{output}/{subject}_L_{older_timepoint}-{younger_timepoint}."
        right_file_prefix = fr"{output}/{subject}_R_{older_timepoint}-{younger_timepoint}."
        script_output_l = path.join(temp_output, f"Subject_{subject}_L_{older_timepoint}-{younger_timepoint}_MSM.sh")
        script_output_r = path.join(temp_output, f"Subject_{subject}_R_{older_timepoint}-{younger_timepoint}_MSM.sh")
        
        if is_local:
            print(f"{datetime.now()}[INFO] Local flag used. Using local run templates")
            template_path_l = path.join(template_dir, "MSM_template_reverse_L_local.txt")
            template_path_r = path.join(template_dir, "MSM_template_reverse_R_local.txt")
            template_dict_l = {
                "levels": levels,
                "config": config,
                "yss": left_younger_spherical_surface,
                "oss": left_older_spherical_surface,
                "yc": left_younger_curvature,
                "oc": left_older_curvature,
                "yas": left_younger_anatomical_surface,
                "oas": left_older_anatomical_surface,
                "r_out": left_file_prefix,
                "maxanat": max_anat,
                "maxcp": max_cp,
            }
            template_dict_r = {
                "levels": levels,
                "config": config,
                "yss": right_younger_spherical_surface,
                "oss": right_older_spherical_surface,
                "yc": right_younger_curvature,
                "oc": right_older_curvature,
                "yas": right_younger_anatomical_surface,
                "oas": right_older_anatomical_surface,
                "r_out": right_file_prefix,
                "maxanat": max_anat,
                "maxcp": max_cp,
            }
        else:
            print(f"{datetime.now()}[INFO] Local flag not used, using remote templates")
            template_path_l = path.join(template_dir, "MSM_template_reverse_L.txt")
            template_path_r = path.join(template_dir, "MSM_template_reverse_R.txt")
            template_dict_l = {
                "subject": subject,
                "starting_time": older_timepoint,
                "ending_time": younger_timepoint,
                "user_home": user_home,
                "email": slurm_email,
                "account": slurm_account,
                "levels": levels,
                "config": config,
                "yss": left_younger_spherical_surface,
                "oss": left_older_spherical_surface,
                "yc": left_younger_curvature,
                "oc": left_older_curvature,
                "yas": left_younger_anatomical_surface,
                "oas": left_older_anatomical_surface,
                "r_out": left_file_prefix,
                "maxanat": max_anat,
                "maxcp": max_cp,
            }
            template_dict_r = {
                "subject": subject,
                "starting_time": older_timepoint,
                "ending_time": younger_timepoint,
                "user_home": user_home,
                "email": slurm_email,
                "account": slurm_account,
                "levels": levels,
                "config": config,
                "yss": right_younger_spherical_surface,
                "oss": right_older_spherical_surface,
                "yc": right_younger_curvature,
                "oc": right_older_curvature,
                "yas": right_younger_anatomical_surface,
                "oas": right_older_anatomical_surface,
                "r_out": right_file_prefix,
                "maxanat": max_anat,
                "maxcp": max_cp,
            }
            
        
    print(f"{datetime.now()}[INFO] left file prefix is: {left_file_prefix}")
    print(f"{datetime.now()}[INFO] right file prefix is: {right_file_prefix}")
    print(f"{datetime.now()}[INFO] Scripts will be generated at {script_output_l} and {script_output_r}")
    print(f"{datetime.now()}[INFO] Left template: {template_path_l}")
    print(f"{datetime.now()}[INFO] Right template: {template_path_r}")
    
    # ------------------
    # Remote Templates
    # ------------------
    if not is_local:
        # ------------------------
        # Left Hemisphere Remote
        # ------------------------
        print(f"{datetime.now()}[STEP] Generateing left hemisphere script")
        print(f"{datetime.now()}[INFO] Using the following info for template")
        print(f"    Template: {template_path_l}")
        for k,v in template_dict_l.items():
            print(f"    {k}: {v}")
        
        print(f"{datetime.now()}[FUNCTION] generate_from_template(template_path=template_path_l, output_path=script_output_l, template_dict=template_dict_l)")
        generate_from_template(template_path=template_path_l, output_path=script_output_l, template_dict=template_dict_l)
        print()
        
        # -------------------------
        # Right Hemisphere Remote
        # -------------------------
        print(f"{datetime.now()}[STEP] Generateing right hemisphere script")
        print(f"{datetime.now()}[INFO] Using the following info for template")
        print(f"    Template: {template_path_r}")
        for k,v in template_dict_r.items():
            print(f"    {k}: {v}")
        
        print(f"{datetime.now()}[FUNCTION] generate_from_template(template_path=template_path_r, output_path=script_output_r, template_dict=template_dict_r)")
        generate_from_template(template_path=template_path_r, output_path=script_output_r, template_dict=template_dict_r)
        print()
                            
    # -----------------
    # Local Templates
    # -----------------
    elif is_local:
        if hemisphere is None or hemisphere not in {"L", "R"}:
            fail("Local runs must indicate which hemisphere to be run using 'L' or 'R'")
        elif hemisphere == "L":
            # -----------------------
            # Left Hemisphere Local
            # -----------------------
            
            print(f"{datetime.now()}[INFO] Using the following info for template")
            print(f"    Template: {template_path_l}")
            for k,v in template_dict_l.items():
                print(f"    {k}: {v}")
            
            print(f"{datetime.now()}[FUNCTION] generate_from_template(template_path=template_path_l, output_path=script_output_l, template_dict=template_dict_l)")
            generate_from_template(template_path=template_path_l, output_path=script_output_l, template_dict=template_dict_l)
            print()
            
                
        elif hemisphere == "R":
            # -----------------------
            # Right Hemisphere Local
            # -----------------------            
            print(f"{datetime.now()}[INFO] Using the following info for template")
            print(f"    Template: {template_path_r}")
            for k,v in template_dict_r.items():
                print(f"    {k}: {v}")
            
            print(f"{datetime.now()}[FUNCTION] generate_from_template(template_path=template_path_r, output_path=script_output_r, template_dict=template_dict_r)")
            generate_from_template(template_path=template_path_r, output_path=script_output_r, template_dict=template_dict_r)
            print()

    # ------------------------
    #  Submit Remote Jobs
    # ------------------------
    if not is_local:
        print(f"{datetime.now()}[STEP] Submitting remote jobs to Slurm")
        # -----------------
        # Left Hemisphere
        # -----------------
        print(f"{datetime.now()}[INFO] Script to submit: {script_output_l}")
        if slurm_job_limit == None:
            print(f"{datetime.now()}[INFO] No job limit provided, using default")
            print(f"{datetime.now()}[FUNCTION] is_slurm_queue_open(slurm_user=slurm_user)")
            jobs_open = is_slurm_queue_open(slurm_user=slurm_user)
            print()
        else:
            print(f"{datetime.now()}[INFO] Checking Slurm with a job limit of {slurm_job_limit}")
            print(f"{datetime.now()}[FUNCTION] is_slurm_queue_open(slurm_user=slurm_user, slurm_job_limit=slurm_job_limit)")
            jobs_open = is_slurm_queue_open(slurm_user=slurm_user, slurm_job_limit=slurm_job_limit)
            print()
        while jobs_open <= 0:
            print(f"{datetime.now()}[INFO] No jobs currently open. Waiting two hours then checking again.")
            sleep(2 * 3600)
            if slurm_job_limit == None:
                print(f"{datetime.now()}[INFO] No job limit provided, using default")
                print(f"{datetime.now()}[FUNCTION] is_slurm_queue_open(slurm_user=slurm_user)")
                jobs_open = is_slurm_queue_open(slurm_user=slurm_user)
                print()
            else:
                print(f"{datetime.now()}[INFO] Checking Slurm with a job limit of {slurm_job_limit}")
                print(f"{datetime.now()}[FUNCTION] is_slurm_queue_open(slurm_user=slurm_user, slurm_job_limit=slurm_job_limit)")
                jobs_open = is_slurm_queue_open(slurm_user=slurm_user, slurm_job_limit=slurm_job_limit)
                print()
        print(f"{datetime.now()}[INFO]Jobs open submitting script")
        run_logged(fr"sbatch {script_output_l}", step="SUBMIT REMOTE")
        print(f"{datetime.now()}[INFO] Deleting {script_output_l}")
        remove(script_output_l)
        
        # ------------------
        # Right Hemisphere
        # ------------------
        print(f"{datetime.now()}[INFO] Script to submit: {script_output_r}")
        if slurm_job_limit == None:
            print(f"{datetime.now()}[INFO] No job limit provided, using default")
            print(f"{datetime.now()}[FUNCTION] is_slurm_queue_open(slurm_user=slurm_user)")
            jobs_open = is_slurm_queue_open(slurm_user=slurm_user)
            print()
        else:
            print(f"{datetime.now()}[INFO] Checking Slurm with a job limit of {slurm_job_limit}")
            print(f"{datetime.now()}[FUNCTION] is_slurm_queue_open(slurm_user=slurm_user, slurm_job_limit=slurm_job_limit)")
            jobs_open = is_slurm_queue_open(slurm_user=slurm_user, slurm_job_limit=slurm_job_limit)
            print()
        while jobs_open <= 0:
            print(f"{datetime.now()}[INFO] No jobs currently open. Waiting two hours then checking again.")
            sleep(2 * 3600)
            if slurm_job_limit == None:
                print(f"{datetime.now()}[INFO] No job limit provided, using default")
                print(f"{datetime.now()}[FUNCTION] is_slurm_queue_open(slurm_user=slurm_user)")
                jobs_open = is_slurm_queue_open(slurm_user=slurm_user)
                print()
            else:
                print(f"{datetime.now()}[INFO] Checking Slurm with a job limit of {slurm_job_limit}")
                print(f"{datetime.now()}[FUNCTION] is_slurm_queue_open(slurm_user=slurm_user, slurm_job_limit=slurm_job_limit)")
                jobs_open = is_slurm_queue_open(slurm_user=slurm_user, slurm_job_limit=slurm_job_limit)
                print()
        print(f"{datetime.now()}[INFO]Jobs open submitting script")
        run_logged(fr"sbatch {script_output_r}", step="SUBMIT REMOTE")
        print(f"{datetime.now()}[INFO] Deleting {script_output_r}")
        remove(script_output_r)
    
    # -------------------
    # Run Local Scripts
    # -------------------
    elif is_local:
        print(f"{datetime.now()}[STEP] Running script locally")
        if hemisphere == "L":
            print(f"{datetime.now()}[INFO] Script to run: {script_output_l}")
            run_logged(fr"bash {temp_output}/Subject_{subject}_L_{younger_timepoint}-{older_timepoint}_MSM.sh", step="RUN MSM")
            print(f"{datetime.now()}[INFO] Deleting {script_output_r}")
            remove(fr"{temp_output}/Subject_{subject}_L_{younger_timepoint}-{older_timepoint}_MSM.sh")
        elif hemisphere == "R":
            print(f"{datetime.now()}[INFO] Script to run: {script_output_r}")
            run_logged(fr"bash {temp_output}/Subject_{subject}_R_{younger_timepoint}-{older_timepoint}_MSM.sh", step="RUN MSM")
            print(f"{datetime.now()}[INFO] Deleting {script_output_r}")
            remove(fr"{temp_output}/Subject_{subject}_R_{younger_timepoint}-{older_timepoint}_MSM.sh")
    if is_local:
        print(f"{datetime.now()}[COMPLETE] MSM registration complete")
    else:
        print(f"{datetime.now()}[COMPLETE] MSM jobs for submitted to slurm")
            

# Function for MSM BL to all
def run_msm_bl_to_all(dataset: str, output: str, starting_time: str, slurm_account: str, slurm_user: str,
                      slurm_email: str, alphanumeric_timepoints: bool=False, time_point_number_start_character: int | None=None,
                      younger_uses_mcribs: bool=False, older_uses_mcribs: bool=False, slurm_job_limit: int | None=None, levels: int=6, config: str | None=None,
                      max_anat: str | None=None, max_cp: str | None=None, use_rescaled: bool=False):
    # --------------------------
    # Batch Run MSM BL to All
    # --------------------------
    print(f"\n{datetime.now()}[MSM BL TO ALL] Beginning batch run for subjects in dataset {dataset} starting from time point {starting_time}")
    print(f"{datetime.now()}[INFO] Arguments passed:")
    for name, value in locals().items():
        print(f"    {name}: {value}")
        
    print(f"{datetime.now()}[STEP] Retrieving subjects from dataset {dataset}")
    print(f"{datetime.now()}[FUNCTION] get_subjects(dataset=dataset)")
    subjects = get_subjects(dataset=dataset)
    print()
    
    print(f"{datetime.now()}[STEP] Submitting MSM jobs")
    for subject in subjects:
        print(f"{datetime.now()}[INFO] Retrieving timepoints for {subject}")
        print(f"{datetime.now()}[FUNCTION] get_subject_time_points(dataset=dataset, subject=subject, alphanumeric_timepoints=alphanumeric_timepoints, time_point_number_start_character=time_point_number_start_character, starting_time=starting_time)")
        time_points = get_subject_time_points(dataset=dataset, subject=subject, alphanumeric_timepoints=alphanumeric_timepoints, time_point_number_start_character=time_point_number_start_character, starting_time=starting_time)
        print()
        
        if starting_time not in time_points:
            print(f"{datetime.now()}[WARN] Starting Time missing for subejct {subject}. Proceeding to next subject")
            continue
        
        print(f"{datetime.now()}[INFO] Submit runs to run_msm")
        for time_point in time_points:
            if time_point != starting_time:
                print(f"{datetime.now()}[INFO] Starting forward run")
                print(f'{datetime.now()}[FUNCTION] run_msm(dataset=dataset, output=output, subject=subject, younger_timepoint=starting_time, older_timepoint=time_point, mode="forward", younger_uses_mcribs=younger_uses_mcribs, older_uses_mcribs=older_uses_mcribs, levels=levels, config=config, max_anat=max_anat, max_cp=max_cp, slurm_email=slurm_email, slurm_account=slurm_account, slurm_user=slurm_user, slurm_job_limit=slurm_job_limit, use_rescaled=use_rescaled)')
                run_msm(dataset=dataset, output=output, subject=subject, younger_timepoint=starting_time, older_timepoint=time_point, mode="forward", younger_uses_mcribs=younger_uses_mcribs, older_uses_mcribs=older_uses_mcribs, levels=levels, config=config, max_anat=max_anat, max_cp=max_cp, slurm_email=slurm_email, slurm_account=slurm_account, slurm_user=slurm_user, slurm_job_limit=slurm_job_limit, use_rescaled=use_rescaled)
                print()
                print(f"{datetime.now()}[INFO] Starting reverse run")
                print(f'{datetime.now()}[FUNCTION] run_msm(dataset=dataset, output=output, subject=subject, younger_timepoint=starting_time, older_timepoint=time_point, mode="reverse", younger_uses_mcribs=younger_uses_mcribs, older_uses_mcribs=older_uses_mcribs, levels=levels, config=config, max_anat=max_anat, max_cp=max_cp, slurm_email=slurm_email, slurm_account=slurm_account, slurm_user=slurm_user, slurm_job_limit=slurm_job_limit, use_rescaled=use_rescaled)')
                run_msm(dataset=dataset, output=output, subject=subject, younger_timepoint=starting_time, older_timepoint=time_point, mode="reverse", younger_uses_mcribs=younger_uses_mcribs, older_uses_mcribs=older_uses_mcribs, levels=levels, config=config, max_anat=max_anat, max_cp=max_cp, slurm_email=slurm_email, slurm_account=slurm_account, slurm_user=slurm_user, slurm_job_limit=slurm_job_limit, use_rescaled=use_rescaled)
                print()
    print(f"{datetime.now()}[COMPLETE] Completed batch run")


# Function to run MSM on shirt time windows
def run_msm_short_time_windows(dataset: str, output: str, slurm_account: str, slurm_user: str, slurm_email: str, 
                               alphanumeric_timepoints: bool = False, time_point_number_start_character: int | None=None,
                               younger_uses_mcribs: bool=False, older_uses_mcribs: bool=False, slurm_job_limit: int | None=None, levels: int=6,
                               config: str | None=None, max_anat: str | None=None, max_cp: str | None=None,
                               starting_time: str | None=None, use_rescaled: bool=False):
    # ----------------------------------
    # Batch Run MSM Short Time Windows
    # ----------------------------------
    print(f"\n{datetime.now()}[Run MSM Short Time Windows] Batch running MSM with short time windows from dataset {dataset}")
    for name, value in locals().items():
        print(f"    {name}: {value}")
        
    print(f"{datetime.now()}[STEP] Getting subjects from dataset")
    print(f"{datetime.now()}[FUNCTION] get_subjects(dataset=dataset)")
    subjects = get_subjects(dataset=dataset)
    print()
    
    print(f"{datetime.now()}[STEP] Submitting MSM jobs")
    for subject in subjects:
        print(f"{datetime.now()}[INFO] Getting time points for {subject}")
        print(f"{datetime.now()}[FUNCTION] get_subject_time_points(dataset=dataset, subject=subject, alphanumeric_timepoints=alphanumeric_timepoints, time_point_number_start_character=time_point_number_start_character, starting_time=starting_time)")
        time_points = get_subject_time_points(dataset=dataset, subject=subject, alphanumeric_timepoints=alphanumeric_timepoints, time_point_number_start_character=time_point_number_start_character, starting_time=starting_time)
        print()
        
        print(f"{datetime.now()}[INFO] Iterateing over time points to submit jobs")
        for i, time_point in enumerate(time_points):
            if i + 1 >= len(time_points):
                break
            younger_time = time_point
            older_time = time_points[i + 1]
            if younger_time != starting_time and older_time != starting_time:
                print(f"{datetime.now()}[INFO] submitting job between time points {younger_time} and {older_time}")
                print(f"{datetime.now()}[INFO] Submitting forward job")
                print(f'{datetime.now()}[FUNCTION] run_msm(dataset=dataset, output=output, subject=subject, younger_timepoint=younger_time, older_timepoint=older_time, mode="forward", younger_uses_mcribs=younger_uses_mcribs, older_uses_mcribs=older_uses_mcribs, is_local=False, hemisphere=None, levels=levels, config=config, max_anat=max_anat, max_cp=max_cp, slurm_email=slurm_email, slurm_account=slurm_account, slurm_user=slurm_user, slurm_job_limit=slurm_job_limit, use_rescaled=use_rescaled)')
                run_msm(dataset=dataset, output=output, subject=subject, younger_timepoint=younger_time, older_timepoint=older_time, mode="forward", younger_uses_mcribs=younger_uses_mcribs, older_uses_mcribs=older_uses_mcribs, is_local=False, hemisphere=None, levels=levels, config=config, max_anat=max_anat, max_cp=max_cp, slurm_email=slurm_email, slurm_account=slurm_account, slurm_user=slurm_user, slurm_job_limit=slurm_job_limit, use_rescaled=use_rescaled)
                print()
                print(f"{datetime.now()}[INFO] Submitting reverse job")
                print(f'{datetime.now()}[FUNCTION] run_msm(dataset=dataset, output=output, subject=subject, younger_timepoint=younger_time, older_timepoint=older_time, mode="reverse", younger_uses_mcribs=younger_uses_mcribs, older_uses_mcribs=older_uses_mcribs, is_local=False, hemisphere=None, levels=levels, config=config, max_anat=max_anat, max_cp=max_cp, slurm_email=slurm_email, slurm_account=slurm_account, slurm_user=slurm_user, slurm_job_limit=slurm_job_limit, use_rescaled=use_rescaled)')
                run_msm(dataset=dataset, output=output, subject=subject, younger_timepoint=younger_time, older_timepoint=older_time, mode="reverse", younger_uses_mcribs=younger_uses_mcribs, older_uses_mcribs=older_uses_mcribs, is_local=False, hemisphere=None, levels=levels, config=config, max_anat=max_anat, max_cp=max_cp, slurm_email=slurm_email, slurm_account=slurm_account, slurm_user=slurm_user, slurm_job_limit=slurm_job_limit, use_rescaled=use_rescaled)
                print()
    print(f"{datetime.now()}[COMPLETE] Finished bacth submission for dataset {dataset}")


# Function to generate average maps
def generate_avg_maps(pre_msm_data: str, msm_data: str, subject: str, younger_timepoint: str, older_timepoint: str, max_cp: str | None=None, max_anat: str | None=None, younger_uses_mcribs: bool=False, older_uses_mcribs: bool=False):
    print(f"\n{datetime.now()}[AVG MAPS] Generating average maps for subject={subject} ({younger_timepoint} → {older_timepoint})\n")
    
    # -------------------------
    # Setup defaults
    # -------------------------
    print(f"{datetime.now()}[STEP] Setting up defaults and output directories")
    if max_cp == None:
        script_dir = path.dirname(path.realpath(__file__))
        max_cp = path.join(script_dir, "NeededFiles", "ico5sphere.LR.reg.surf.gii")
    if max_anat == None:
        script_dir = path.dirname(path.realpath(__file__))
        max_anat = path.join(script_dir, "NeededFiles", "ico6sphere.LR.reg.surf.gii")
        
    msm_avg_output = path.join(
        msm_data, f"{subject}_{younger_timepoint}_to_{older_timepoint}_avg")
    makedirs(msm_avg_output, exist_ok=True)
    
    print(f"{datetime.now()}[INFO] Output directory: {msm_avg_output}")
    print(f"{datetime.now()}[INFO] max_cp: {max_cp}")
    print(f"{datetime.now()}[INFO] max_anat: {max_anat}")

    # -------------------------
    # Locate input files
    # -------------------------
    print(f"{datetime.now()}[STEP] Locating input files")
    if younger_uses_mcribs:
        print(f"{datetime.now()}[INFO] Younger timepoint uses MCRIBS pipeline")
        print(f"{datetime.now()}[FUNCTION] Calling get_files_mcribs dataset={pre_msm_data} subject={subject}, timepoint={younger_timepoint}")
        younger_files = get_files_mcribs(pre_msm_data, subject, younger_timepoint)
        print()
    else:
        print(f"{datetime.now()}[INFO] Younger timepoint uses standard pipeline")
        print(f"{datetime.now()}[FUNCTION] Calling get_files dataset={pre_msm_data} subject={subject}, timepoint={younger_timepoint}")
        younger_files = get_files(pre_msm_data, subject, younger_timepoint)
        print()
    
    if older_uses_mcribs:
        print(f"{datetime.now()}[INFO] Older timepoint uses MCRIBS pipeline")
        print(f"{datetime.now()}[FUNCTION] Calling get_files_mcribs dataset={pre_msm_data} subject={subject}, timepoint={older_timepoint}")
        older_files = get_files_mcribs(pre_msm_data, subject, older_timepoint)
        print()
    else:
        print(f"{datetime.now()}[INFO] Older timepoint uses standard pipeline")
        print(f"{datetime.now()}[FUNCTION] Calling get_files dataset={pre_msm_data} subject={subject}, timepoint={older_timepoint}")
        older_files = get_files(pre_msm_data, subject, older_timepoint)
        print()
        
    left_younger_spherical_surface = younger_files["LSS"]
    left_older_spherical_surface = older_files["LSS"]
    right_younger_spherical_surface = younger_files["RSS"]
    right_older_spherical_surface = older_files["RSS"]
    
    print(f"{datetime.now()}[FILES] Selected spherical surfaces:")
    print(f"    Younger L: {left_younger_spherical_surface}")
    print(f"    Younger R: {right_younger_spherical_surface}")
    print(f"    Older   L: {left_older_spherical_surface}")
    print(f"    Older   R: {right_older_spherical_surface}")

    # -------------------------
    # MSM folders
    # -------------------------
    print(f"{datetime.now()}[STEP] Defining MSM forward and reverse folders")
    msm_reverse_folder = path.join(msm_data, f"{subject}_{older_timepoint}_to_{younger_timepoint}")
    msm_forward_folder = path.join(msm_data, f"{subject}_{younger_timepoint}_to_{older_timepoint}")
    print(f"{datetime.now()}[INFO] Reverse folder: {msm_reverse_folder}")
    print(f"{datetime.now()}[INFO] Forward folder: {msm_forward_folder}")
    
    # -------------------------
    # Intermediary file definitions
    # -------------------------
    print(f"{datetime.now()}[STEP] Defining intermediary files")
    left_base_sphere_reverse = path.join(msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.sphere.reg.surf.gii")
    right_base_sphere_reverse = path.join(msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.sphere.reg.surf.gii")
    left_cpgrid_sphere_reverse = path.join(msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.sphere.CPgrid.reg.surf.gii")
    right_cpgrid_sphere_reverse = path.join(msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.sphere.CPgrid.reg.surf.gii")
    left_anatgrid_sphere_reverse = path.join(msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.sphere.ANATgrid.reg.surf.gii")
    right_anatgrid_sphere_reverse = path.join(msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.sphere.ANATgrid.reg.surf.gii")
    left_cpgrid_surfdist_reverse = path.join(msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.surfdist.CPgrid.func.gii")
    left_older_anatomical_surface_cpgrid = path.join(msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.LOAS.CPgrid.surf.gii")
    left_older_anatomical_surface_anatgrid = path.join(msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.LOAS.ANATgrid.surf.gii")
    left_anatgrid_surfdist_reverse = path.join(msm_reverse_folder, f"{subject}_L_{older_timepoint}-{younger_timepoint}.surfdist.ANATgrid.func.gii")
    right_older_anatomical_surface_cpgrid = path.join(msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.ROAS.CPgrid.surf.gii")
    right_older_anatomical_surface_anatgrid = path.join(msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.ROAS.ANATgrid.surf.gii")
    right_cpgrid_surfdist_reverse = path.join(msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.surfdist.CPgrid.func.gii")
    right_anatgrid_surfdist_reverse = path.join(msm_reverse_folder, f"{subject}_R_{older_timepoint}-{younger_timepoint}.surfdist.ANATgrid.func.gii")
    
    print(f"{datetime.now()}[FILES] Reverse registration inputs:")
    print(f"    L sphere: {left_base_sphere_reverse}")
    print(f"    R sphere: {right_base_sphere_reverse}")
    print(f"    L CP sphere: {left_cpgrid_sphere_reverse}")
    print(f"    R CP sphere: {right_cpgrid_sphere_reverse}")
    print(f"    L ANAT sphere: {left_anatgrid_sphere_reverse}")
    print(f"    R ANAT sphere: {right_anatgrid_sphere_reverse}")
    print(f"    L CP surfdist:   {left_cpgrid_surfdist_reverse}")
    print(f"    R CP surfdist:   {right_cpgrid_surfdist_reverse}")
    print(f"    L ANAT surfdist: {left_anatgrid_surfdist_reverse}")
    print(f"    R ANAT surfdist: {right_anatgrid_surfdist_reverse}")
    print(f"    L CP anat surf:  {left_older_anatomical_surface_cpgrid}")
    print(f"    R CP anat surf:  {right_older_anatomical_surface_cpgrid}")
    print(f"    L ANAT surf:     {left_older_anatomical_surface_anatgrid}")
    print(f"    R ANAT surf:     {right_older_anatomical_surface_anatgrid}")
    
    left_base_sphere_forward = path.join(msm_forward_folder, f"{subject}_L_{younger_timepoint}-{older_timepoint}.sphere.reg.surf.gii")
    right_base_sphere_forward = path.join(msm_forward_folder, f"{subject}_R_{younger_timepoint}-{older_timepoint}.sphere.reg.surf.gii")
    left_cpgrid_sphere_forward = path.join(msm_forward_folder, f"{subject}_L_{younger_timepoint}-{older_timepoint}.sphere.CPgrid.reg.surf.gii")
    right_cpgrid_sphere_forward = path.join(msm_forward_folder, f"{subject}_R_{younger_timepoint}-{older_timepoint}.sphere.CPgrid.reg.surf.gii")
    left_anatgrid_sphere_forward = path.join(msm_forward_folder, f"{subject}_L_{younger_timepoint}-{older_timepoint}.sphere.ANATgrid.reg.surf.gii")
    right_anatgrid_sphere_forward = path.join(msm_forward_folder, f"{subject}_R_{younger_timepoint}-{older_timepoint}.sphere.ANATgrid.reg.surf.gii")
    left_cpgrid_surfdist_forward = path.join(msm_forward_folder, f"{subject}_L_{younger_timepoint}-{older_timepoint}.surfdist.CPgrid.func.gii")
    left_anatgrid_surfdist_forward = path.join(msm_forward_folder, f"{subject}_L_{younger_timepoint}-{older_timepoint}.surfdist.ANATgrid.func.gii")
    right_cpgrid_surfdist_forward = path.join(msm_forward_folder, f"{subject}_R_{younger_timepoint}-{older_timepoint}.surfdist.CPgrid.func.gii")
    right_anatgrid_surfdist_forward = path.join(msm_forward_folder, f"{subject}_R_{younger_timepoint}-{older_timepoint}.surfdist.ANATgrid.func.gii")
    
    print(f"{datetime.now()}[FILES] Forward registration inputs:")
    print(f"    L sphere: {left_base_sphere_forward}")
    print(f"    R sphere: {right_base_sphere_forward}")
    print(f"    L CP sphere: {left_cpgrid_sphere_forward}")
    print(f"    R CP sphere: {right_cpgrid_sphere_forward}")
    print(f"    L ANAT sphere: {left_anatgrid_sphere_forward}")
    print(f"    R ANAT sphere: {right_anatgrid_sphere_forward}")
    print(f"    L CP surfdist:   {left_cpgrid_surfdist_forward}")
    print(f"    R CP surfdist:   {right_cpgrid_surfdist_forward}")
    print(f"    L ANAT surfdist: {left_anatgrid_surfdist_forward}")
    print(f"    R ANAT surfdist: {right_anatgrid_surfdist_forward}")
    
    left_revfor_base_sphere = f"{msm_avg_output}/{subject}_L_{older_timepoint}-{younger_timepoint}.revfor.sphere.reg.surf.gii"
    right_revfor_base_sphere = f"{msm_avg_output}/{subject}_R_{older_timepoint}-{younger_timepoint}.revfor.sphere.reg.surf.gii"
    left_revfor_cpgrid_sphere = f"{msm_avg_output}/{subject}_L_{older_timepoint}-{younger_timepoint}.revfor.sphere.CPgrid.reg.surf.gii"
    right_revfor_cpgrid_sphere = f"{msm_avg_output}/{subject}_R_{older_timepoint}-{younger_timepoint}.revfor.sphere.CPgrid.reg.surf.gii"
    left_revfor_anatgrid_sphere = f"{msm_avg_output}/{subject}_L_{older_timepoint}-{younger_timepoint}.revfor.sphere.ANATgrid.reg.surf.gii"
    right_revfor_anatgrid_sphere = f"{msm_avg_output}/{subject}_R_{older_timepoint}-{younger_timepoint}.revfor.sphere.ANATgrid.reg.surf.gii"
    
    print(f"{datetime.now()}[FILES] RevFor outputs (spheres):")
    print(f"    L base: {left_revfor_base_sphere}")
    print(f"    R base: {right_revfor_base_sphere}")
    print(f"    L CP:   {left_revfor_cpgrid_sphere}")
    print(f"    R CP:   {right_revfor_cpgrid_sphere}")
    print(f"    L ANAT: {left_revfor_anatgrid_sphere}")
    print(f"    R ANAT: {right_revfor_anatgrid_sphere}")
    
    left_avgfor_base_sphere = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.sphere.reg.surf.gii"
    right_avgfor_base_sphere = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.sphere.reg.surf.gii"
    left_avgfor_cpgrid_sphere = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.sphere.CPgrid.reg.surf.gii"
    right_avgfor_cpgrid_sphere = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.sphere.CPgrid.reg.surf.gii"
    left_avgfor_anatgrid_sphere = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.sphere.ANATgrid.reg.surf.gii"
    right_avgfor_anatgrid_sphere = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.sphere.ANATgrid.reg.surf.gii"
    
    print(f"{datetime.now()}[FILES] AvgFor outputs (spheres):")
    print(f"    L base: {left_avgfor_base_sphere}")
    print(f"    R base: {right_avgfor_base_sphere}")
    print(f"    L CP:   {left_avgfor_cpgrid_sphere}")
    print(f"    R CP:   {right_avgfor_cpgrid_sphere}")
    print(f"    L ANAT: {left_avgfor_anatgrid_sphere}")
    print(f"    R ANAT: {right_avgfor_anatgrid_sphere}")
    
    left_avgfor_cpgrid_anat = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.anat.CPgrid.reg.surf.gii"
    right_avgfor_cpgrid_anat = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.anat.CPgrid.reg.surf.gii"
    left_avgfor_anatgrid_anat = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.anat.ANATgrid.reg.surf.gii"
    right_avgfor_anatgrid_anat = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.anat.ANATgrid.reg.surf.gii"
    
    print(f"{datetime.now()}[FILES] AvgFor anatomical outputs:")
    print(f"    L CP:   {left_avgfor_cpgrid_anat}")
    print(f"    R CP:   {right_avgfor_cpgrid_anat}")
    print(f"    L ANAT: {left_avgfor_anatgrid_anat}")
    print(f"    R ANAT: {right_avgfor_anatgrid_anat}")
    
    left_revfor_cpgrid_surfdist = f"{msm_avg_output}/{subject}_L_{older_timepoint}-{younger_timepoint}.revfor.surfdist.CPgrid.reg.func.gii"
    left_revfor_anatgrid_surfdist = f"{msm_avg_output}/{subject}_L_{older_timepoint}-{younger_timepoint}.revfor.surfdist.ANATgrid.reg.func.gii"
    right_revfor_cpgrid_surfdist = f"{msm_avg_output}/{subject}_R_{older_timepoint}-{younger_timepoint}.revfor.surfdist.CPgrid.reg.func.gii"
    right_revfor_anatgrid_surfdist = f"{msm_avg_output}/{subject}_R_{older_timepoint}-{younger_timepoint}.revfor.surfdist.ANATgrid.reg.func.gii"
    
    print(f"{datetime.now()}[FILES] Surface distribution maps (RevFor):")
    print(f"    L CP:   {left_revfor_cpgrid_surfdist}")
    print(f"    R CP:   {right_revfor_cpgrid_surfdist}")
    print(f"    L ANAT: {left_revfor_anatgrid_surfdist}")
    print(f"    R ANAT: {right_revfor_anatgrid_surfdist}")
    
    left_avgfor_cpgrid_surfdist = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.surfdist.CPgrid.reg.func.gii"
    left_avgfor_anatgrid_surfdist = f"{msm_avg_output}/{subject}_L_{younger_timepoint}-{older_timepoint}.avgfor.surfdist.ANATgrid.reg.func.gii"
    right_avgfor_cpgrid_surfdist = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.surfdist.CPgrid.reg.func.gii"
    right_avgfor_anatgrid_surfdist = f"{msm_avg_output}/{subject}_R_{younger_timepoint}-{older_timepoint}.avgfor.surfdist.ANATgrid.reg.func.gii"
    
    print(f"{datetime.now()}[FILES] Surface distribution maps (AvgFor):")
    print(f"    L CP:   {left_avgfor_cpgrid_surfdist}")
    print(f"    R CP:   {right_avgfor_cpgrid_surfdist}")
    print(f"    L ANAT: {left_avgfor_anatgrid_surfdist}")
    print(f"    R ANAT: {right_avgfor_anatgrid_surfdist}")

    
    # -------------------------
    # Generate RevFor spheres
    # -------------------------
    print(f"{datetime.now()}[STEP] Generating revfor spheres")
    run_logged(f"wb_command -surface-sphere-project-unproject {left_older_spherical_surface} {left_base_sphere_reverse} {left_younger_spherical_surface} {left_revfor_base_sphere}", step="REVFOR_SPHERE")
    run_logged(f"wb_command -surface-sphere-project-unproject {right_older_spherical_surface} {right_base_sphere_reverse} {right_younger_spherical_surface} {right_revfor_base_sphere}", step="REVFOR_SPHERE")
    run_logged(f"wb_command -surface-sphere-project-unproject {max_cp} {left_cpgrid_sphere_reverse} {max_cp} {left_revfor_cpgrid_sphere}", step="REVFOR_SPHERE")
    run_logged(f"wb_command -surface-sphere-project-unproject {max_cp} {right_cpgrid_sphere_reverse} {max_cp} {right_revfor_cpgrid_sphere}", step="REVFOR_SPHERE")
    run_logged(f"wb_command -surface-sphere-project-unproject {max_anat} {left_anatgrid_sphere_reverse} {max_anat} {left_revfor_anatgrid_sphere}", step="REVFOR_SPHERE")
    run_logged(f"wb_command -surface-sphere-project-unproject {max_anat} {right_anatgrid_sphere_reverse} {max_anat} {right_revfor_anatgrid_sphere}", step="REVFOR_SPHERE")
    
    # -------------------------
    # Generate AvgFor spheres
    # -------------------------
    print(f"{datetime.now()}[STEP] Generating avgfor spheres")
    run_logged(f"wb_command -surface-average {left_avgfor_base_sphere} -surf {left_base_sphere_forward} -surf {left_revfor_base_sphere}", step="AVGFOR_SPHERE")
    run_logged(f"wb_command -surface-average {right_avgfor_base_sphere} -surf {right_base_sphere_forward} -surf {right_revfor_base_sphere}", step="AVGFOR_SPHERE")
    run_logged(f"wb_command -surface-average {left_avgfor_cpgrid_sphere} -surf {left_cpgrid_sphere_forward} -surf {left_revfor_cpgrid_sphere}", step="AVGFOR_SPHERE")
    run_logged(f"wb_command -surface-average {right_avgfor_cpgrid_sphere} -surf {right_cpgrid_sphere_forward} -surf {right_revfor_cpgrid_sphere}", step="AVGFOR_SPHERE")
    run_logged(f"wb_command -surface-average {left_avgfor_anatgrid_sphere} -surf {left_anatgrid_sphere_forward} -surf {left_revfor_anatgrid_sphere}", step="AVGFOR_SPHERE")
    run_logged(f"wb_command -surface-average {right_avgfor_anatgrid_sphere} -surf {right_anatgrid_sphere_forward} -surf {right_revfor_anatgrid_sphere}", step="AVGFOR_SPHERE")

    # -------------------------
    # Recenter spheres
    # -------------------------
    print(f"{datetime.now()}[STEP] Recentering avgfor spheres")
    run_logged(f"wb_command -surface-modify-sphere -recenter {left_avgfor_base_sphere} 100 {left_avgfor_base_sphere}", step="RECENTER_AVGFOR")
    run_logged(f"wb_command -surface-modify-sphere -recenter {right_avgfor_base_sphere} 100 {right_avgfor_base_sphere}", step="RECENTER_AVGFOR")
    run_logged(f"wb_command -surface-modify-sphere -recenter {left_avgfor_cpgrid_sphere} 100 {left_avgfor_cpgrid_sphere}", step="RECENTER_AVGFOR")
    run_logged(f"wb_command -surface-modify-sphere -recenter {right_avgfor_cpgrid_sphere} 100 {right_avgfor_cpgrid_sphere}", step="RECENTER_AVGFOR")
    run_logged(f"wb_command -surface-modify-sphere -recenter {left_avgfor_anatgrid_sphere} 100 {left_avgfor_anatgrid_sphere}", step="RECENTER_AVGFOR")
    run_logged(f"wb_command -surface-modify-sphere -recenter {right_avgfor_anatgrid_sphere} 100 {right_avgfor_anatgrid_sphere}", step="RECENTER_AVGFOR")

    # -------------------------
    # Generate avgfor anatomical surfaces
    # -------------------------
    print(f"{datetime.now()}[STEP] Generating aavgfor anatomical surfaces")
    run_logged(f"wb_command -surface-resample {left_older_anatomical_surface_cpgrid} {max_cp} {left_avgfor_cpgrid_sphere} \"BARYCENTRIC\" {left_avgfor_cpgrid_anat}", step="AVGFOR_AS")
    run_logged(f"wb_command -surface-resample {right_older_anatomical_surface_cpgrid} {max_cp} {right_avgfor_cpgrid_sphere} \"BARYCENTRIC\" {right_avgfor_cpgrid_anat}", step="AVGFOR_AS")
    run_logged(f"wb_command -surface-resample {left_older_anatomical_surface_anatgrid} {max_anat} {left_avgfor_anatgrid_sphere} \"BARYCENTRIC\" {left_avgfor_anatgrid_anat}", step="AVGFOR_AS")
    run_logged(f"wb_command -surface-resample {right_older_anatomical_surface_anatgrid} {max_anat} {right_avgfor_anatgrid_sphere} \"BARYCENTRIC\" {right_avgfor_anatgrid_anat}", step="AVGFOR_AS")

    # -------------------------
    # Generate revfor surfdist
    # -------------------------
    print(f"{datetime.now()}[STEP] Generating revfor surface distorion maps")
    run_logged(f"wb_command -metric-math 'X*-1' {left_revfor_cpgrid_surfdist} -var X {left_cpgrid_surfdist_reverse}", step="REVFOR_SURFDIST")
    run_logged(f"wb_command -metric-math 'X*-1' {left_revfor_anatgrid_surfdist} -var X {left_anatgrid_surfdist_reverse}", step="REVFOR_SURFDIST")
    run_logged(f"wb_command -metric-math 'X*-1' {right_revfor_cpgrid_surfdist} -var X {right_cpgrid_surfdist_reverse}", step="REVFOR_SURFDIST")
    run_logged(f"wb_command -metric-math 'X*-1' {right_revfor_anatgrid_surfdist} -var X {right_anatgrid_surfdist_reverse}", step="REVFOR_SURFDIST")

    # -------------------------
    # Average surfdist
    # -------------------------
    print(f"{datetime.now()}[STEP] Computing average surface distorion maps")
    run_logged(f"wb_command -metric-math '(J1+J2)/2' {left_avgfor_cpgrid_surfdist} -var J1 {left_revfor_cpgrid_surfdist} -var J2 {left_cpgrid_surfdist_forward}", step="AVGFOR_SURFDIST")
    run_logged(f"wb_command -metric-math '(J1+J2)/2' {left_avgfor_anatgrid_surfdist} -var J1 {left_revfor_anatgrid_surfdist} -var J2 {left_anatgrid_surfdist_forward}", step="AVGFOR_SURFDIST")
    run_logged(f"wb_command -metric-math '(J1+J2)/2' {right_avgfor_cpgrid_surfdist} -var J1 {right_revfor_cpgrid_surfdist} -var J2 {right_cpgrid_surfdist_forward}", step="AVGFOR_SURFDIST")
    run_logged(f"wb_command -metric-math '(J1+J2)/2' {right_avgfor_anatgrid_surfdist} -var J1 {right_revfor_anatgrid_surfdist} -var J2 {right_anatgrid_surfdist_forward}", step="AVGFOR_SURFDIST")

    # -------------------------
    # Set Structue Average
    # -------------------------
    print(f"{datetime.now()}[STEP] Setting structure of avgfor surface distortion maps")
    run_logged(f"wb_command -set-structure {left_avgfor_cpgrid_surfdist} CORTEX_LEFT", step="STRUCTURE")
    run_logged(f"wb_command -set-structure {left_avgfor_anatgrid_surfdist} CORTEX_LEFT", step="STRUCTURE")
    run_logged(f"wb_command -set-structure {right_avgfor_cpgrid_surfdist} CORTEX_RIGHT", step="STRUCTURE")
    run_logged(f"wb_command -set-structure {right_avgfor_anatgrid_surfdist} CORTEX_RIGHT", step="STRUCTURE")

    print(f"{datetime.now()}[COMPLETE] Average map generation finished")


# Function to run all average maps
def generate_avg_maps_all(pre_msm_data: str, msm_data: str, max_cp: str | None=None, max_anat: str | None=None, starting_time: str | None=None, uses_mcribs: bool=False):
    print(f"\n{datetime.now()}[AVG MAPS ALL] Scanning MSM directory: {msm_data}\n")
    
    # -------------------------
    # Setup defaults
    # -------------------------
    print(f"{datetime.now()}[STEP] Setting up defaults and templates")

    if max_cp == None:
        script_dir = path.dirname(path.realpath(__file__))
        max_cp = path.join(script_dir, "NeededFiles", "ico5sphere.LR.reg.surf.gii")
        print(f"{datetime.now()}[INFO] max_cp not provided → using default: {max_cp}")

    if max_anat == None:
        script_dir = path.dirname(path.realpath(__file__))
        max_anat = path.join(script_dir, "NeededFiles", "ico6sphere.LR.reg.surf.gii")
        print(f"{datetime.now()}[INFO] max_anat not provided → using default: {max_anat}")

    print(f"{datetime.now()}[INFO] max_cp: {max_cp}")
    print(f"{datetime.now()}[INFO] max_anat: {max_anat}")

    # -------------------------
    # Scan directories
    # -------------------------
    print(f"{datetime.now()}[STEP] Scanning MSM output directories")

    directories = listdir(msm_data)
    print(f"{datetime.now()}[INFO] Found {len(directories)} entries")

    for directory in directories:
        print("----------------------------------------")
        print(f"{datetime.now()}[INFO] Processing directory: {directory}")

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

        print(f"{datetime.now()}[INFO] Parsing metadata from directory")
        print(f"    subject={subject}")
        print(f"    first_time={first_time} first_month={first_month}")
        print(f"    second_time={second_time} second_month={second_month}")

        # -------------------------
        # Filtering logic (unchanged)
        # -------------------------
        print(f"{datetime.now()}[INFO] Evaluating processing conditions")

        if first_time == starting_time:
            print(f"{datetime.now()}[INFO] SKIP condition met: first_time={first_time} == starting_time={starting_time}")
            continue

        elif second_time == starting_time:
            print(f"{datetime.now()}[INFO] MATCH condition met: second_time={second_time} == starting_time={starting_time}")

            if uses_mcribs:
                print(f"{datetime.now()}[FUNCTION] generate_avg_maps(pre_msm_data={pre_msm_data}, msm_data={msm_data}, subject={subject}, younger_timepoint={second_time}, older_timepoint={first_time}, max_cp={max_cp}, max_anat={max_anat}, younger_uses_mcribs=True, older_uses_mcribs=True)")
                generate_avg_maps(pre_msm_data, msm_data, subject, second_time, first_time, max_cp, max_anat, True, True)
                print()
            else:
                print(f"{datetime.now()}[FUNCTION] generate_avg_maps(pre_msm_data={pre_msm_data}, msm_data={msm_data}, subject={subject}, younger_timepoint={second_time}, older_timepoint={first_time}, max_cp={max_cp}, max_anat={max_anat})")
                generate_avg_maps(pre_msm_data, msm_data, subject, second_time, first_time, max_cp, max_anat)
                print()

        elif first_month < second_month:
            print(f"{datetime.now()}[INFO] SKIP condition met: first_month={first_month} < second_month={second_month} (already processed direction)")
            continue

        elif second_month < first_month:
            print(f"{datetime.now()}[INFO] MATCH condition met: second_month={second_month} < first_month={first_month}")

            if uses_mcribs:
                print(f"{datetime.now()}[FUNCTION] generate_avg_maps(pre_msm_data={pre_msm_data}, msm_data={msm_data}, subject={subject}, younger_timepoint={second_time}, older_timepoint={first_time}, max_cp={max_cp}, max_anat={max_anat}, younger_uses_mcribs=True, older_uses_mcribs=True)")
                generate_avg_maps(pre_msm_data, msm_data, subject, second_time, first_time, max_cp, max_anat, True, True)
                print()
            else:
                print(f"{datetime.now()}[FUNCTION] generate_avg_maps(pre_msm_data={pre_msm_data}, msm_data={msm_data}, subject={subject}, younger_timepoint={second_time}, older_timepoint={first_time}, max_cp={max_cp}, max_anat={max_anat})")
                generate_avg_maps(pre_msm_data, msm_data, subject, second_time, first_time, max_cp, max_anat)
                print()

    print(f"{datetime.now()}[COMPLETE] Finished generating all average maps")


# Rescale mcribs surface
def rescale_surfaces(dataset: str,  subject: str, time_point: str, uses_mcribs: bool=False):
    # ------------------
    # Rescale Surfaces
    # ------------------
    print(f"\n{datetime.now()}[RESCALE] Begin rescaling for subject {subject} at time point {time_point}")
    
    # ----------------
    # Retrieve Files
    # ----------------
    print(f"{datetime.now()}[STEP]Retriving subject files")
    if uses_mcribs:
        print(f"{datetime.now()}[FUNCTION] get_files_mcribs(dataset=dataset, subject=subject, time_point=time_point)")
        subject_files = get_files_mcribs(dataset=dataset, subject=subject, time_point=time_point)
        print()
    else:
        print(f"{datetime.now()}[FUNCTION] get_files(dataset=dataset, subject=subject, time_point=time_point)")
        subject_files = get_files(dataset=dataset, subject=subject, time_point=time_point)
        print()
    
    left_midthickness_file = subject_files["LAS"]
    right_midthickness_file = subject_files["RAS"]
    subject_dir = subject_files["SUBJECT DIR"]
    subject_prefix = subject_files["SUBJECT PREFIX"]
    script_dir = path.dirname(path.realpath(__file__))
    max_anat = path.join(script_dir, "NeededFiles", "ico6sphere.LR.reg.surf.gii")
    max_cp = path.join(script_dir, "NeededFiles", "ico5sphere.LR.reg.surf.gii")
    print(f"{datetime.now()}[INFO] Files found:")
    print(f"    Subject directory: {subject_dir}")
    print(f"    Subject prefix: {subject_prefix}")
    print(f"    Left midthickness file: {left_midthickness_file}")
    print(f"    Right midthickness file: {right_midthickness_file}")
    # left_cortex = subject_files["LEFT CORTEX"]
    # right_cortex = subject_files["RIGHT CORTEX"]
    
    
    left_shape_file = path.join(subject_dir, f"{subject_prefix}.L.areas.shape.gii")
    right_shape_file = path.join(subject_dir, f"{subject_prefix}.R.areas.shape.gii")
    left_affine_matrix = path.join(subject_dir, f"{subject_prefix}.L.rescaleaffine.nii")
    right_affine_matrix = path.join(subject_dir, f"{subject_prefix}.R.rescaleaffine.nii")
    left_rescaled_surface = path.join(subject_dir, f"{subject_prefix}.L.rescaled.surf.gii")
    right_rescaled_surface = path.join(subject_dir, f"{subject_prefix}.R.rescaled.surf.gii")
    left_resampled_surface_anatgrid = path.join(subject_dir, f"{subject_prefix}.L.rescaled.ANATgrid.surf.gii")
    right_resampled_surface_anatgrid = path.join(subject_dir, f"{subject_prefix}.R.rescaled.ANATgrid.surf.gii")
    left_resampled_surface_cpgrid = path.join(subject_dir, f"{subject_prefix}.L.rescaled.CPgrid.surf.gii")
    right_resampled_surface_cpgrid = path.join(subject_dir, f"{subject_prefix}.R.rescaled.CPgrid.surf.gii")
    
    # -------------------
    # Create shape files
    # -------------------
    print(f"{datetime.now()}[STEP] Creating shape files")
    run_logged(f"wb_command -surface-vertex-areas {left_midthickness_file} {left_shape_file}")
    run_logged(f"wb_command -surface-vertex-areas {left_midthickness_file} {right_shape_file}")
    
    # ------------------------
    # Calculate Surface area
    # ------------------------
    print(f"{datetime.now()}[STEP] Calculating surface areas")
    run_logged(f"wb_command -metric-stats {left_shape_file} -reduce SUM")
    command_output = run(f"wb_command -metric-stats {left_shape_file} -reduce SUM", shell=True, capture_output=True, text=True, check=True)
    left_surface_area = float(command_output.stdout.strip())
    
    run_logged(f"wb_command -metric-stats {right_shape_file} -reduce SUM")
    command_output = run(f"wb_command -metric-stats {right_shape_file} -reduce SUM", shell=True, capture_output=True, text=True, check=True)
    right_surface_area = float(command_output.stdout.strip())
    print(f"{datetime.now()}[INFO] Left Surface Area: {left_surface_area}")
    print(f"{datetime.now()}[INFO] Right Surface Area: {right_surface_area}")
    
    # -------------------------
    # Calculate Rescale Value
    # -------------------------
    print(f"{datetime.now()}[STEP] Calculating rescale values")
    left_rescale_value = sqrt(10000 / left_surface_area)
    right_rescale_value = sqrt(10000 / right_surface_area)
    print(f"{datetime.now()}[INFO] Left Rescale Value: {left_rescale_value}")
    print(f"{datetime.now()}[INFO] Right Rescale Value: {right_rescale_value}")
    
    # ---------------------
    # Apply affine rescale
    # ----------------------
    print(f"{datetime.now()}[STEP] Creating affine matrices")
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
        
    
    print(f"{datetime.now()}[STEP] Applying affine matrices to surfaces")
    run_logged(f"wb_command -surface-apply-affine {left_midthickness_file} {left_affine_matrix} {left_rescaled_surface}")
    run_logged(f"wb_command -surface-apply-affine {right_midthickness_file} {right_affine_matrix} {right_rescaled_surface}")
    
    # ------------------
    # Generate Spheres
    # ------------------
    print(f"{datetime.now()}[STEP] Generating new spheres for rescaled surfaces")
    print(f"{datetime.now()}[INFO] Input files and options:")
    print(f"    SUBJECT DIR: {subject_dir}")
    print(f"    SUBJECT PREFIX: {subject_prefix}")
    print(f"    LEFT MIDTHICKNESS: {left_midthickness_file}")
    print(f"    RIGHT MIDTHICKNESS: {right_midthickness_file}")
    print(f"    MAX ANAT: {max_anat}")
    print(f"{datetime.now()}[FUNCTION] generate_sphere(subject_dir=subject_dir, subject_prefix=subject_prefix, left_midthickness=left_midthickness_file, right_midthickness=right_midthickness_file, max_anat=max_anat)")
    left_spherical_surface, right_spherical_surface = generate_sphere(subject_dir=subject_dir, subject_prefix=subject_prefix, left_midthickness=left_midthickness_file, right_midthickness=right_midthickness_file, max_anat=max_anat)
    print()
    
    # -----------------------
    # Resample to anat grid
    # -----------------------
    print(f"{datetime.now()}[STEP] Resampling rescaled surfaces")
    print(f"{datetime.now()}[INFO] Input Files:")
    print(f"    LEFT RESCALED SURFACE: {left_rescaled_surface}")
    print(f"    RIGHT RESCALED SURFACE: {right_rescaled_surface}")
    print(f"    LEFT SPHERE: {left_spherical_surface}")
    print(f"    RIGHT SPHERE: {right_spherical_surface}")
    print(f"    MAX ANAT: {max_anat}")
    print(f"    MAX CP: {max_cp}")
    
    print(f"{datetime.now()}[INFO] Output Files:")
    print(f"    LEFT RESAMLPED SURFACE ANATGRID: {left_resampled_surface_anatgrid}")
    print(f"    RIGHT RESAMLPED SURFACE ANATGRID: {right_resampled_surface_anatgrid}")
    print(f"    LEFT RESAMLPED SURFACE CPGRID: {left_resampled_surface_cpgrid}")
    print(f"    RIGHT RESAMLPED SURFACE CPGRID: {right_resampled_surface_cpgrid}")
    
    print(f"{datetime.now()}[INFO] Start resample to ANATgrid")
    run_logged(f'wb_command -surface-resample {left_rescaled_surface} {left_spherical_surface} {max_anat} "BARYCENTRIC" {left_resampled_surface_anatgrid}', step="RESAMPLE ANAT")
    print(f"{datetime.now()}[INFO] Left hemisphere complete")
    run_logged(f'wb_command -surface-resample {right_rescaled_surface} {right_spherical_surface} {max_anat} "BARYCENTRIC" {right_resampled_surface_anatgrid}', step="RESAMPLE ANAT")
    print(f"{datetime.now()}[INFO] Right hemisphere complete")
    
    print(f"{datetime.now()}[INFO] Start resample to CPgrid")
    run_logged(f'wb_command -surface-resample {left_rescaled_surface} {left_spherical_surface} {max_cp} "BARYCENTRIC" {left_resampled_surface_cpgrid}', step="RESAMPLE CP")
    print(f"{datetime.now()}[INFO] Left hemisphere complete")
    run_logged(f'wb_command -surface-resample {right_rescaled_surface} {right_spherical_surface} {max_cp} "BARYCENTRIC" {right_resampled_surface_cpgrid}', step="RESAMPLE CP")
    print(f"{datetime.now()}[INFO] Right hemispher complete")
    
    print(f"{datetime.now()}[COMPLETE] Rescaling complete")


# Rescale surfaces for all subjects
def rescale_surfaces_all(dataset: str, uses_mcribs: bool=True):
    print(f"\n{datetime.now()}[RESCALE ALL] Rescaling all surfaces in dataset {dataset}")
    for subject_folder in listdir(dataset):
        subject_path = path.join(dataset, subject_folder)
        if path.isdir(subject_path):
            fields = subject_folder.split("_")
            subject = fields[1]
            time_point = fields[2]
            print(f"{datetime.now()}[INFO] Rescale subject {subject} at time point {time_point}")
            print(f"{datetime.now()}[FUNCTION] rescale_surfaces(dataset=dataset, subject=subject, time_point=time_point, uses_mcribs=uses_mcribs)")
            rescale_surfaces(dataset=dataset, subject=subject, time_point=time_point, uses_mcribs=uses_mcribs)
            print()
            
            
# function to retrieve files for mcribs subject
def get_files_mcribs(dataset: str, subject: str, time_point: str, is_rescaled=False):
    print(f"\n{datetime.now()}[GET FILES] Getting files for Subject {subject} at time point {time_point} in {dataset}, using M-CRIB-S naming conventions")
    
    # -------------------------
    # Set up variables
    # -------------------------
    subject_dir = path.join(dataset, f"Subject_{subject}_{time_point}")
    print(f"{datetime.now()}[STEP] Searching for files in {subject_dir}")
    
    # --------------------------
    # Search for files
    # --------------------------
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="lh.midthickness.surf.gii", search_path=subject_dir)')
    left_anatomical_surface = find(patterns=[f"lh.{subject}{time_point}_midthickness_711-2N_rot.surf.gii", f"lh.{subject}{time_point}_midthickness_711-2B_rot.surf.gii", f"lh.{subject}{time_point}_midthickness_711-2N.surf.gii", f"lh.{subject}{time_point}_midthickness_711-2B.surf.gii", "lh.midthickness.surf.gii"], search_path=subject_dir)
    print()
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="rh.midthickness.surf.gii", search_path=subject_dir)')
    right_anatomical_surface = find(patterns=[f"rh.{subject}{time_point}_midthickness_711-2N_rot.surf.gii", f"rh.{subject}{time_point}_midthickness_711-2B_rot.surf.gii", f"rh.{subject}{time_point}_midthickness_711-2N.surf.gii", f"rh.{subject}{time_point}_midthickness_711-2B.surf.gii", "rh.midthickness.surf.gii"], search_path=subject_dir)
    print()
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="lh.sphere.reg2.surf.gii", search_path=subject_dir)')
    left_spherical_surface = find(patterns="lh.sphere.reg2.surf.gii", search_path=subject_dir)
    print()
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="rh.sphere.reg2.surf.gii", search_path=subject_dir)')
    right_spherical_surface = find(patterns="rh.sphere.reg2.surf.gii", search_path=subject_dir)
    print()
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="lh.curv.shape.gii", search_path=subject_dir)')
    left_curvature = find(patterns="lh.curv.shape.gii", search_path=subject_dir)
    print()
    
    print(f'{datetime.now()}[FUNCTION] find(patterns="rh.curv.shape.gii", search_path=subject_dir)')
    right_curvature = find(patterns="rh.curv.shape.gii", search_path=subject_dir)
    print()
    
    #print(f'{datetime.now()}[FUNCTION] find(patterns="lh.mean.thickness", search_path=subject_dir)')
    left_cortex = None # TODO Figure out what this should be
    #print()
    
    #print(f'{datetime.now()}[FUNCTION] find(patterns="rh.mean.thickness", search_path=subject_dir)')
    right_cortex = None # TODO Figure out what this should be
    #print()
    
    # ---------------------------------------------
    # Grab rescaled and resampled files if needed
    #----------------------------------------------
    if is_rescaled:
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.L.rescaled.surf.gii", search_path=subject_dir)')
        left_rescaled_surface = find(patterns="*.L.rescaled.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.R.rescaled.surf.gii", search_path=subject_dir)')
        right_rescaled_surface = find(patterns="*.R.rescaled.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.L.generated.sphere.surf.gii", search_path=subject_dir)')
        left_generated_sphere = find(patterns="*.L.generated.sphere.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.R.generated.sphere.surf.gii", search_path=subject_dir)')
        right_generated_sphere = find(patterns="*.R.generated.sphere.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.L.rescaled.ANATgrid.surf.gii", search_path=subject_dir)')
        left_resampled_anatgrid=find(patterns="*.L.rescaled.ANATgrid.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.L.rescaled.CPgrid.surf.gii", search_path=subject_dir)')
        left_resampled_cpgrid=find(patterns="*.L.rescaled.CPgrid.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.L=R.rescaled.ANATgrid.surf.gii", search_path=subject_dir)')
        right_resampled_anatgrid=find(patterns="*.R.rescaled.ANATgrid.surf.gii", search_path=subject_dir)
        print()
        
        print(f'{datetime.now()}[FUNCTION] find(patterns="*.R.rescaled.CPgrid.surf.gii", search_path=subject_dir)')
        right_resampled_cpgrid=find(patterns="*.R.rescaled.CPgrid.surf.gii", search_path=subject_dir)
        print()
    else:
        left_rescaled_surface = right_rescaled_surface = left_generated_sphere = right_generated_sphere = left_resampled_anatgrid = right_resampled_anatgrid = left_resampled_cpgrid = right_resampled_cpgrid = None
    
    #-----------------
    # Return Files
    #-----------------
    subject_files = {
        "LAS": left_anatomical_surface,
        "RAS": right_anatomical_surface,
        "LSS": left_spherical_surface,
        "RSS": right_spherical_surface,
        "LEFT CURVATURE": left_curvature,
        "RIGHT CURVATURE": right_curvature,
        "SUBJECT DIR": subject_dir,
        "SUBJECT PREFIX": subject,
        "LEFT CORTEX": left_cortex,
        "RIGHT CORTEX": right_cortex,
        "LEFT RESCALE": left_rescaled_surface,
        "RIGHT RESCALE": right_rescaled_surface,
        "LEFT RESCALE ANAT": left_resampled_anatgrid,
        "LEFT RESCALE CP": left_resampled_cpgrid,
        "RIGHT RESCALE ANAT": right_resampled_anatgrid,
        "RIGHT RESCALE CP": right_resampled_cpgrid,
        "LEFT GEN SPHERE": left_generated_sphere,
        "RIGHT GEN SPHERE": right_generated_sphere,
    }
    
    print(f"{datetime.now()}[INFO] Returniing these files:")
    for k,v in subject_files.items():
        print(f"    {k}: {v}")
        
    print(f"{datetime.now()}[COMPLETE] Found all files for subject {subject}, at time point {time_point}, in {dataset}. Returning dictonary of files")
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
    
    run_logged(f"mris_convert -c {left_curv} {left_white_matter} {left_output}")
    run_logged(f"mris_convert -c {right_curv} {right_white_matter} {right_output}")
    

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
    run_logged(f"wb_command -surface-sphere-project-unproject {left_sphere_in} {sphere_project_to} {left_sphere_unproject_from} {left_concat_output}")
    run_logged(f"wb_command -surface-sphere-project-unproject {right_sphere_in} {sphere_project_to} {right_sphere_unproject_from} {right_concat_output}")
    
    run_logged(f"wb_command -surface-resample {left_as_time_end} {spherical_surface} {left_concat_output} 'BARYCENTRIC' {left_anat_output}")
    run_logged(f"wb_command -surface-resample {right_as_time_end} {spherical_surface} {right_concat_output} 'BARYCENTRIC' {right_anat_output}")
    
    run_logged(f"wb_command -surface-distortion {left_surface_reference} {left_anat_output} {left_surfdist_output}")
    run_logged(f"wb_command -surface-distortion {right_surface_reference} {right_anat_output} {right_surfdist_output}")
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
            run_logged(f"wb_command -surface-sphere-project-unproject {left_sphere_in} {sphere_project_to} {left_sphere_unproject_from} {left_concat_output}")
            run_logged(f"wb_command -surface-sphere-project-unproject {right_sphere_in} {sphere_project_to} {right_sphere_unproject_from} {right_concat_output}")
            
            run_logged(f"wb_command -surface-resample {left_as_time_end} {spherical_surface} {left_concat_output} 'BARYCENTRIC' {left_anat_output}")
            run_logged(f"wb_command -surface-resample {right_as_time_end} {spherical_surface} {right_concat_output} 'BARYCENTRIC' {right_anat_output}")
            
            run_logged(f"wb_command -surface-distortion {left_surface_reference} {left_anat_output} {left_surfdist_output}")
            run_logged(f"wb_command -surface-distortion {right_surface_reference} {right_anat_output} {right_surfdist_output}")
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
    gam.add_argument("--pre_msm_data", required=True, help="Path to data from ciftify run")
    gam.add_argument("--msm_data", required=True, help="Path to MSM registrations")
    gam.add_argument("--subject", required=True, help="Subject ID to generate average maps")
    gam.add_argument("--younger_timepoint", required=True, help="The younger time point of the registration")
    gam.add_argument("--older_timepoint", required=True, help="The older time point of the registration")
    gam.add_argument("--max_cp", required=False, help="Path to MaxCP reference sphere, typically ico5sphere")
    gam.add_argument("--max_anat", required=False, help="Path to MaxANAT reference sphere, typically ico6sphere")
    gam.add_argument("--younger_uses_mcribs", action="store_true", help="Use if the younger time point is from an mcribs dataset")
    gam.add_argument("--older_uses_mcribs", action="store_true", help="Use if the older time point is from an mcribs dataset")
        
    # Generate All Avg Maps
    raa = subparser.add_parser("generate_avg_maps_all", help="Run average map generation on all subjects")
    raa.add_argument("--pre_msm_data", required=True, help="Path to data from ciftify run")
    raa.add_argument("--msm_data", required=True, help="Path to MSM registrations")
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
