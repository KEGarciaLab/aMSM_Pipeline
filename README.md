<!-- Improved compatibility of back to top link: See: https://github.com/othneildrew/Best-README-Template/pull/73 -->
<a name="readme-top"></a>
<!--
*** Thanks for checking out the Best-README-Template. If you have a suggestion
*** that would make this better, please fork the repo and create a pull request
*** or simply open an issue with the tag "enhancement".
*** Don't forget to give the project a star!
*** Thanks again! Now go create something AMAZING! :D
-->



<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
-->
[![Contributors][contributors-shield]][contributors-url]
[![Issues][issues-shield]][issues-url]
[![Stars][stars-shield]][stars-url]


<h3 align="center">aMSM_Pipeline</h3>

  <p align="center">
    Processing scripts for aMSM analysis.
    <br />
    <a href="https://github.com/KEGarciaLab/aMSM_AD"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/KEGarciaLab/aMSM_AD/issues">Report Bug</a>
    ·
    <a href="https://github.com/KEGarciaLab/aMSM_AD/issues">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
<ul>
    <li><a href="#usage-guideline"></a> Usage Guidelines</li>
    <li><a href="#naming-conventions">A note on naming conventions</a></li>
    <li><a href="#get-ciftify-subject-list">get_ciftify_subject_list</a></li>
    <li><a href="#is-slurm-queue-open">is_slurm_queue_open</a></li>
    <li><a href="#run-cifitify">run_cifitify</a></li>
    <li><a href="#get-subject-time-points">get_subject_time_points</a></li>
    <li><a href="#rescale-surfaces">rescale_surfaces</a></li>
    <li><a href="#generate_qc_image">generate_qc_image</a></li>
    <li><a href="#qc_all">qc_all</a></li>
    <li><a href="#generate-post-processing-image">generate_post_processing_image</a></li>
    <li><a href="#post-process-all">post_process_all</a></li>
    <li><a href="#run-msm">run_msm</a></li>
    <li><a href="#run-msm-bl-to-all">run_msm_bl_to_all</a></li>
    <li><a href="#run-msm-short-time-windows">run_msm_short_time_windows</a></li>
    <li><a href="#generate-avg-maps">generate_avg_maps</a></li>
    <li><a href="#generate-avg-maps-all">generate_avg_maps_all</a></li>
    <li><a href="#convert-curvature">convert_curvature</a></li>
    <li><a href="#convert-curvature-all">convert_curvature_all</a></li>
    <li><a href="#concatenate_registrations">concatenate_registrations</a></li>
</ul>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
### About The Project
---

Processing scripts for aMSM analysis of Alzheimer's Disease data.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- GETTING STARTED -->
### Getting Started
---

To get started with using these tools for the instructions below to install them.


### Installation
To use this tool you must have ciftify, conectome workbench, MSM_HOCR, and Python 3.11 installed already. Follow install instructions for each tool and their dependencies. Once those are installed you can download the release .zip file from here, extract it, and run the installer.sh file. This installs the pipeline, all dependencies and the necessary files. You can ensure installation by using `MSM_Pipeline -h` in a bash terminal. IF you do not get the help message for the pipeline, ensure that the files are located in $HOME/bin and that $HOME/bin is added to PATH.

#### DEPRECATED

All scripts used for installation of the various tools can be found in the Installation folder of the repo. They should be ran in the order listed below to avoid errors. It is also recommended that you either reboot your system or reconnect through an ssh after each installation to ensure it was completed properly. Finally, these installation scripts were made assuming this would be ran on one of the IU supercomputing clusters. If you are outside of IU or are not using one of these systems you will need to install MSM, Ciftify, and Conetome Workbench manually, including updating `.bash_profile` in order to add the commands to PATH.

```sh
bash InstallationScripts/MSM-install.sh
```
```sh
bash InstallationScripts/Ciftify-install.sh
```
```sh
bash InstallationScripts/Workbench-install.sh
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
### Usage
---

The entire pipeline has been bundled into a single Python script with a command line interface. The easiest way to use this pipeline is to follow the install instructions so that it is added to PATH and can be used as a command. Once completed, I would then reccomend creating a simple shell script to run any command you wish. While all commands can be run from a bash terminal directly, the commands can be very long witha  alot of arguments; using a shell script allows for a more readable version of the command to make troubleshooting easier. Below, I have detailed the various commands avaliable within the pipeline as well as the arguments needed for each one. Note that every argument is a keyword and not positional so you must have the flag, but the order does not matter. `-h` can be used after any command name to see all arguments needed for any command.

<a name="usage-guidelines"></a>
### Usage Guidelines
---
This pipeline has three modes of operation depending on if the data has used Freesurfer or M-CRIB-S. If the data has used freesurfer your general usage is running ciftify, optinal qc image generation, msm forward and reverse, generate average maps, and finally optional post processing. If the data is from M-CRIB-S the general flow is to convert curvature files, rescale surfaces, optional qc, msm forward and reverse, and finally optional post processing. For subjects were M-CRIB-S was used for one time point and Freesurfer was used on the other the general usage is run ciftify on freesurfer data, convert curvature for M-CRIB-S data, rescale M-CRIB-S data, optional qc, run msm forwards and reverse, and finally optional post processing. Note that currently average map generation for M-CRIB-S files is in development.

<a name='naming-conventions'></a>
### A note on naming conventions
---
This pipeline was orginally designed to start with freesurfer output and go through ciftify then msm. Due to this everything except the ciftify related commands have specific naming convention requirements. If you are starting from data that has already been ran through ciftify or data from M-CRIB-S you must have the data in a folder following the convention of `subject_<subjetc-id>_<timepoint>`. Once this has been done all tools are ready to be used

<a name="is-slurm-queue-open"></a>
### `is_slurm_queue_open`
---
Checks the slurm queue of the specified user and returns the number of open jobs. Also prints the queue to a .txt file. Note that this assumes a job limit of 500. The slurm queue can still be checked manually 
#### Arguments
##### Required:
* `--slurm_user` The username of the user to check the queue for.

##### Optional:
* `--slurm_job_limit` The users job limit in slurm. Defaults to 500 if not specified

<a name="get-ciftify-subject-list"></a>
### `get_ciftify_subject_list`
---
This command is used to retrive a list of all folders of subject data that need to converted using `run_ciftify`.
#### Arguments
##### Required:
* `--dataset` The location of the freesurfer data. This should be the root folder containing all the folders of subjects and time points.
* `--subjects` A space separated list of subject IDs that you want to find the folders names for.
* `--pattern` A regex of the format of the folder name in regards to the location of the subeject ID, using "#" as a placeholder for the ID. e.g. `.*_S_#_.*` this will search for folders that contain `_S_<subject_id>_` with the subject ID being pulled from the list of subjects provided.

<a name="run-ciftify"></a>
### `run_ciftify`
---
This command is used to run the `ciftify-recon-all` command on the indicated directories and place the output in the indicated folder. This creates one output directory for each input directory in the indicated output location.
#### Arguments
##### Required:
* `--dataset` This is the folder where your directories are located. Note: there are plans to make this automatic and remove the need for this argument
* `--delimiter` The character used to separate fields in the orginal directory name, typically "_"
* `--subject_index` The location of the subject id based on the delimiter, with the first field being 0
* `--time_index` The same as above but for the time point of the scan
* `--output_path` The full path where you want all of the directories created

##### Optional:
* `--is_local` Use this flag to indicate this will be ran locally. If this is used slurm options are not required
* `--slurm_account` The slurm account ID used for job allocations
* `--slurm_user` Slurm username for checking queue
* `--slurm_email` The email address you wish for failed job notifications to be sent to
* `--slurm_job_limit` The user's slurm job limit. Defaults to 500 if not included

<a name="get-subject-time-points"></a>
### `get_subject_time_points`
--- 
A helper function that lists all time points for a given subject in a given dataset. Useful for troubleshooting.
#### Arguments
##### Required:
* `--dataset` The path to the directory containing subject data.
* `--subject` The subject ID for which timepoints will be retrieved.

##### Optional:
* `--alphanumeric_timepoints` Include this option if your timepoints are alphanumeric
* `--time_point_number_start_character` The character where numbers begin in the timepoint; 0 indexed. Only needed if using `--alphanumeric_timepoints`
* `--starting_time` Provide starting time point if it uses a different naming convention. Can be left out if baseline uses the same naming convention.

<a name="rescsale-surfaces"></a>
### `rescale_surfaces`
---
Generates recaled anatomical surfaces for the indicated subject and time point. This is required for M-CRIB-S data.
#### Arguments
##### Required:
* `--dataset` The path to the directory containing subject data
* `--subject` The subject to be rescaled
* `--time_point` The time_point to be rescaled

<a name="generate_qc_image"></a>
### `generate_qc_image`
---
Generates images for qc before running MSM. Must be in the same output format that the pipeline uses for our ciftify function, and requires at least two different time points per subject
#### Arguments
##### Required:
* `--dataset` The path to directory containing both subject time points
* `--subject` The subject ID for QC
* `--younger_time` The younger time point for QC
* `--older_time` The older time point for QC
* `--output` The folder to place the QC images in

#### Optional:
*`--uses_mcribs` Use if the dataset is from M-CRlB-S.

<a name="qc_all"></a>
### `qc_all`
---
Runs the `generate_qc_image` command on all time point pairs in a given directory
#### Arguments
##### Required:
* `--dataset` The path to directory containing both subject time points
* `--output` The folder to place the QC images in

##### Optional:
* `--alphanumeric_timepoints` Include this flag if your time points use letters and numbers. Defaults to false
* `--time_point_number_start_character` The character where the numbers begin if using alphanumric time points. 0 indexed, defaults to None
* `--starting_time` Use this option if your baseline time point uses a different naming scheme than the other time points. Defaults to None
* *`--uses_mcribs` Use if the dataset is M-CRIB-S.

<a name="generate-post-processing-image"></a>
### `generate_post_processing_image`
--- 
Generates post-processing images based on the directory input.
#### Arguments
##### Required:
* `--subject_directory` The path to the directory in which the created MSM output files should be contained.
* `--resolution` Desired resolution of created images. Either CPgrid or ANATgrid.
* `--mode` Identify forward, reverse, or average depending on registration.
* `--output` Location to which output images will be copied. Images will also be placed in the subject directory.
  
<a name="post-process-all"></a>
### `post_process_all`
--- 
Generates post-processing images for the entirety of the provided dataset.
#### Arguments
##### Required:
* `--dataset` Location of the MSM registrations.
* `--starting_time` The baseline timepoint of data. This value is used to determine whether forward or reverse registration was used.
* `--resolution` Identify resolution of created images. Either CPgrid or ANATgrid.
* `--output` Location to which output images will be copied. Images will also be placed in the subject directory.

<a name="run-msm"></a>
### `run_msm`
---
Runs forward and reverse registrations of the indicated subject and timepoint.
#### Arguments
##### Required:
* `--dataset` Path to the directory containing all time points for registration.
* `--output` Path for the output of MSM files. A seperate folder for each registration will be created at this path.
* `--subject` The subject ID MSM registration.
* `--younger_timepoint` The younger timepoint for registration.
* `--older_timepoint` The older timepoint for registration.
* `--mode` Identify forward or reverse registration mode.

##### Optional:
* `--levels` Identify the levels of MSM to run. See MSM documentation for more information. Defaults to 6
* `--config` Path to the MSM config file to be used. See MSM documentation for more information. Only used if not using default.
* `--max_anat` Path to MaxANAT reference sphere (typically ico6sphere). Only used if not using default.
* `--max_cp` Path to MaxCP reference sphere (typically ico5sphere). Only used if not using default
* `--is_local` include this option if you want to run MSM in a local environment
* `--hemisphere` specify the hemisphere you wish to run msm on when using is_local. Must be L or R and must be included when using is_local
* `--slurm_email` Email to which failed job notifications should be sent. Only used for remote runs.
* `--slurm_account` Slurm account ID for submission. Only used for remote runs.
* `--slurm_user` Slurm username for checking queue. Only used for remote runs.
* `--slurm_job_limit` The user's slurm job limit. Only used for remote runs when slurm job limit is not 500.
* `--younger_uses_mcribs` Use this flag to indicate that M-CRIB-S files need to be used for the younger timepoint
* `--older_uses_mcribs` USe this flag to indicate that M-CRIB-S files need to be used for the older timepoint

<a name="run-msm-bl-to-all"></a>
### `run_msm_bl_to_all`
--- 
Runs MSM registrations, starting at the baseline timepoint, for each other timepoint availible for a given subject. Multiple subjects can be run if they are all included in the specified folder.
#### Arguments
##### Required:
* `--dataset` The path to the directory containing all data for registration.
* `--alphanumeric_timepoints` Identify whether the timepoints are alphanumeric.
* `--time_point_number_start_character` Identify the character where numbers begin in the timepoint; 0 indexed.
* `--output` The path for output of MSM files. A folder for each registration will be created here.
* `--starting_time` The time point used as a baseline ('bl') for all registrations.
* `--slurm_account` The slurm account ID for submission.
* `--slurm_user` Slurm username used for checking the queue.
* `--slurm_email` Email address to which failed job notifications should be sent.

##### Optional:
* `--slurm_job_limit` The user's slurm job limit. Defaults to 500.
* `--levels` Levels of MSM to run. See MSM documentation for more information. Defaults to 6.
* `--config` Path to the MSM config file that will be used. See MSM documentation for more information. Only needed if not using default.
* `--max_anat` Path to the MaxANATreference sphere (typically ico6sphere). Only needed if not using default.
* `--max_cp` Path the the MaxCP reference sphere (typically ico5sphere). Only needed if not using default.
* `--younger_uses_mcribs` Use this flag to indicate that M-CRIB-S files need to be used for the younger timepoint
* `--older_uses_mcribs` Use this flag to indicate that M-CRIB-S files need to be used for the older timepoint

<a name="run-msm-short-time-windows"></a>
### `run_msm_short_time_windows`
--- 
Runs MSM on all subjects in a folder using sequential timepoints.
#### Arguments
##### Required:
* `--dataset` The path to the directory containing all data for registration.
* `--alphanumeric_timepoints` Identify whether the timepoints are alphanumeric.
* `--time_point_number_start_character` The character where numbers begin in the timepoint; 0 indexed.
* `--output` Path for the MSM output files. A folder for each registration will be created here.
* `--slurm_account` The slurm account ID for submission.
* `--slurm_user` The slurm username for checking the queue.
* `--slurm email` The email to which failed job notifications will be sent.

##### Optional:
* `--slurm_job_limit` The user's slurm job limit. Defaults to 500
* `--levels` Levels of MSM that will be run. See MSM documentation for more information. Defaults to 6
* `--config` Path to the MSM config file that will be used. See MSM documentation for more information. Only needed if not using default.
* `--max_anat` Path to the MaxANAT reference sphere (typically ico6sphere). Only needed if not using default.
* `--max_cp` Path to the MaxCP reference sphere (typically ico5sphere). Only needed if not using default.
* `--starting_time` The starting time point. This is only necessary if baseline registrations should be skipped.
* `--younger_uses_mcribs` Use this flag to indicate that M-CRIB-S files need to be used for the younger timepoint
* `--older_uses_mcribs` Use this flag to indicate that M-CRIB-S files need to be used for the older timepoint

<a name="generate-avg-maps"></a>
### `generate_avg_maps`
--- 
Generates an average map for the specified subject and time points.
#### Arguments
##### Required:
* `--ciftify_dataset` Path to the folder containing ciftify outputs.
* `--msm_dataset` Path to MSM registrations.
* `-- subject` The subject ID that will be used to generate average maps.
* `--younger_timepoint` The younger timepoint of the registration.
* `--older_timepoint` The older timepoint of the registration.

#### Optional:
* `--max_cp` Path to the MaxCP reference sphere (typically ico5sphere) if not using provided icosphere files.
* `--max_anat` Path to the MaxANAT reference sphere (typically ico6sphere) if not using provided icosphere files.
* `--younger_uses_mcribs` Used to indicate that the younger time point uses M-CRIB-S data
* `--older_uses_mcribs` Used to indicate that the older time point uses M-CRIB-S data

<a name="generate-avg-maps-all"></a>
### `generate_avg_maps_all`
--- 
Generates average maps for all registrations in the specified directory.
#### Arguments
##### Required:
* `--ciftify_dataset` Path to the folder containing ciftify outputs.
* `--msm_dataset` Path to MSM registration.

#### Optional:
* `--max_cp` Path to the MaxCP reference sphere (typically ico5sphere) if not using provided icosphere files.
* `--max_anat` Path to the MaxANAT reference sphere (typically ico6sphere) if not using provided icosphere files.
* `--starting_time` The baseline time of registrations. This is used to determine which average maps are needed.
* `--uses_mcribs` Used to indicate that the dataset as a whole uses M-CRIB-S. Note that this is only avaliable for datasets which wholly use M-CRIB-S. M-CRIB-S to Freesurfer everage maps muct be generated using the singular function above.

<a name="convert-curvature"></a>
### `convert_curvature`
---
Converts curvature files for a given subject and time point into GIFTI format (`.func.gii`). This is required before running MSM, as the curvature values are used during registration.
#### Arguments
##### Required:
* `--dataset` Path to the directory containing subject data.
* `--subject` The subject ID whose curvature files will be converted.
* `--time_point` The time point of the scan for which curvature conversion will be performed.

<a name="convert-curvature-all"></a>
### `convert_curvature_all`
---
Converts all curvature files in a given dataset into GIFTI format (`.func.gii`).
#### Arguments
##### Required:
* `--dataset` Path to directory containing all subject data

<a name="concatenate-surfaces"></a>
### `concatenate_registrations`
---  
Concatenates MSM registrations across multiple time points to reduce noise in longer registration chains.

#### Arguments
##### Required:
* `--msm_dataset` Path to directory containing MSM registrations; folder should contain directories for each time point needed.
* `--pre_msm_dataset` Path to either the ciftify output or M-CRIB-S data.
* `--subject` Subject ID to concatenate registrations for.
* `--concat_start_time` Starting time point for the concatenation (typically the first registration in the chain).
* `--concat_end_time` Ending time point for the concatenation (typically the last registration in the chain).
* `--resolution` Resolution of registration for concatenation. Choices: `CPgrid` or `ANATgrid`.
* `--output` Path for output of concatenated registrations. A folder for each concatenation will be created here.

##### Optional:
* `--max_anat` Path to MaxAnat reference sphere (typically ico6sphere). Only needed if not using default.
* `--max_cp` Path to MaxCP reference sphere (typically ico5sphere). Only needed if not using default.
* `--alphanumeric_timepoints` Use if the time points are alphanumeric. Time points will be sorted based on the numeric portion of the name (ensure consistency).
* `--time_point_number_start_character` The character index (0-based) where numbers begin in the time point name. Required if using `--alphanumeric_timepoints`.
* `--starting_time` Used if the starting time point uses a different naming convention.



**DEPRECATED**

All scripts provided have a section where various variables can be changed to suit the needs of the user. Be sure to check this section for accuracy before running any scripts. These will mostly be able to guide you through the usage of each one. Further instructions are detailed below.

Once you have installed the verious tools as outlined in the previous step, you are now ready to begin running analysis on the data. To get started you will need to have access to data from at least one subject at two different time points. This pipeline assumes you are starting from raw Freesurfer output. The first step is to use `Ciftify_Subject_List.sh` to generate a txt file with the folder names of the subjects which need to be converted from Freesurfer to HCP format using `ciftify_recon_all`. Note that this script is set up to look for one of two possible naming conventions `*_S_<SUBJECT#>_*` or `<SUBJECT#>_*` as these two naming conventions are the ones used by ADNI and IADRC respectively. If your data is in a different format the script can be easily updated to handle that. Furthermore, if the dataset you wish to test is small enough, you can simply create a txt document manually where the folder name for each folder, without the path, is listed on a seperate line.

After obtaining the txt file of subjects you are now ready to run the `ciftify_recon_all` command on the data to begin the conversion process. In order to simplify this process the script `RunCiftify.sh` should be used. A few things to note: as with all scripts, be sure to check the variable definitions at the top of the script before running. At the very least you will need to update the `SUBJECT_TXT` variable to point to the txt file you just created. Secondly, you will need to provide the script with information about your naming convention. Specifically you will need to provide a `DELIMITER`. This is whatever character is used to seperate fields in the directory name, "\_" is a typical one. You'll also need to provide the `SUBJECT_POSISTION` and `TIME_POINT_POSISTION`. These are simply where in the folder name your subject and time point can be found in regards to the delimiter selector. For example, if your naming convention is `SUBJECT_<SUBJECt#>_<SCAN#>` your positions would be 2 and 3 with a delimiter of "\_". Finally, `ciftify_recon_all` is a very intensive process that takes a very long time to run. As such the script assumes that the work is being done on a high powered cluster computing system through the use of Slurm. If this is not the case the script will again need to be edited to use a different workload manager or to be ran locally. It is strongly advised to not run this script locally as even a single run of the `ciftify_recon_all` command can take upwards of two hours and, since the pipeline requires at least two timepoints, this would subsequently take over 4 hours to complete the full script.

The third step in the pipeline is to run MSM on the dataset. This is accomplished through the use of the `RunMSM.sh` script. As usual ensure that all variables are correct for your system before proceeding. The only special thing to note is that the first timepoint for each subject must be assign using the `STARTING_TIME` variable. This is what ever your naming convention designates as the earliest time point for each subject. It should be unique (only one per subject) and every subject being ran should have this time point. All subjects are assumed to follow the naming convention `Subject_<subject#>_<timepoint>` as these folders are generated in the previous step. As with Ciftify, it is not recommended to run this on a local machine as even a single registration can take upwards of 8 hours, with a single run of the script requiring two regestrations (one forward and one reverse).

Following these steps will get you an output of folders with the maps and surfaces ready to view using Workbench. Other scripts, such as `PostProcessing.sh` and `InvertSurfdist.sh` serve as examples of postprocessing that can be done such as generating images of the registrations through Workbench, or inverting the reverse registration map so that it is the same as the relevant forward registration, useful for eliminating noise. Finally, all extra files can be found in the 'NeededFiles' directory.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
### Contact
---

Project Link: [https://github.com/KEGarciaLab/aMSM_AD](https://github.com/KEGarciaLab/aMSM_AD)

Project Lead: [Dr. Kara Garcia](mailto:karagarc@?subject=[GitHub]aMSM_AD)

Script Manager: [Sammy Rigdon IV](mailto:srigdon5@?subject=[GitHub]aMSM_AD)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
### Acknowledgments
---

* <a href="https://github.com/othneildrew/Best-README-Template"> Read me tepmplate by othneildrew</a>

* This Project is based on scripts and processes developed in the following publication: <a href="https://onlinelibrary.wiley.com/doi/full/10.1002/hbm.25455"> Iannopollo, E., Garcia, K., & Alzheimer's Disease Neuroimaging Initiative. (2021). Enhanced detection of cortical atrophy in Alzheimer's disease using structural MRI with anatomically constrained longitudinal registration. Human Brain Mapping, 42(11), 3576-3592.</a>

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/KEGarciaLab/aMSM_AD.svg?style=for-the-badge
[contributors-url]: https://github.com/KEGarciaLab/aMSM_AD/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/KEGarciaLab/aMSM_AD.svg?style=for-the-badge
[forks-url]: https://github.com/KEGarciaLab/aMSM_AD/network/members
[stars-shield]: https://img.shields.io/github/stars/KEGarciaLab/aMSM_AD.svg?style=for-the-badge
[stars-url]: https://github.com/KEGarciaLab/aMSM_AD/stargazers
[issues-shield]: https://img.shields.io/github/issues/KEGarciaLab/aMSM_AD.svg?style=for-the-badge
[issues-url]: https://github.com/KEGarciaLab/aMSM_AD/issues
[license-shield]: https://img.shields.io/github/license/KEGarciaLab/aMSM_AD.svg?style=for-the-badge
[license-url]: https://github.com/KEGarciaLab/aMSM_AD/blob/master/LICENSE.txt
[product-screenshot]: images/screenshot.png
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/
[React.js]: https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[React-url]: https://reactjs.org/
[Vue.js]: https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D
[Vue-url]: https://vuejs.org/
[Angular.io]: https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white
[Angular-url]: https://angular.io/
[Svelte.dev]: https://img.shields.io/badge/Svelte-4A4A55?style=for-the-badge&logo=svelte&logoColor=FF3E00
[Svelte-url]: https://svelte.dev/
[Laravel.com]: https://img.shields.io/badge/Laravel-FF2D20?style=for-the-badge&logo=laravel&logoColor=white
[Laravel-url]: https://laravel.com
[Bootstrap.com]: https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white
[Bootstrap-url]: https://getbootstrap.com
[JQuery.com]: https://img.shields.io/badge/jQuery-0769AD?style=for-the-badge&logo=jquery&logoColor=white
[JQuery-url]: https://jquery.com 
