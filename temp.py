def generate_avg_maps(pre_msm_data: str, msm_data: str, subject: str, younger_timepoint: str, older_timepoint: str, max_cp: str | None=None, max_anat: str | None=None, younger_uses_mcribs: bool=False, older_uses_mcribs: bool=False):

    # -------------------------
    # MSM folders
    # -------------------------
    print("\n[STEP] Defining MSM forward and reverse folders")

    msm_reverse_folder = path.join(
        msm_data, f"{subject}_{older_timepoint}_to_{younger_timepoint}")
    msm_forward_folder = path.join(
        msm_data, f"{subject}_{younger_timepoint}_to_{older_timepoint}")

    print(f"[INFO] Reverse folder: {msm_reverse_folder}")
    print(f"[INFO] Forward folder: {msm_forward_folder}")

    # -------------------------
    # Generate RevFor spheres
    # -------------------------
    print("\n[STEP] Generating revfor spheres")

    run_logged(f"wb_command -surface-sphere-project-unproject {left_older_spherical_surface} {left_base_sphere_reverse} {left_younger_spherical_surface} {left_revfor_base_sphere}")
    run_logged(f"wb_command -surface-sphere-project-unproject {right_older_spherical_surface} {right_base_sphere_reverse} {right_younger_spherical_surface} {right_revfor_base_sphere}")
    run_logged(f"wb_command -surface-sphere-project-unproject {max_cp} {left_cpgrid_sphere_reverse} {max_cp} {left_revfor_cpgrid_sphere}")
    run_logged(f"wb_command -surface-sphere-project-unproject {max_cp} {right_cpgrid_sphere_reverse} {max_cp} {right_revfor_cpgrid_sphere}")
    run_logged(f"wb_command -surface-sphere-project-unproject {max_anat} {left_anatgrid_sphere_reverse} {max_anat} {left_revfor_anatgrid_sphere}")
    run_logged(f"wb_command -surface-sphere-project-unproject {max_anat} {right_anatgrid_sphere_reverse} {max_anat} {right_revfor_anatgrid_sphere}")

    run_logged(f"wb_command -surface-average {left_avgfor_base_sphere} -surf {left_base_sphere_forward} -surf {left_revfor_base_sphere}")
    run_logged(f"wb_command -surface-average {right_avgfor_base_sphere} -surf {right_base_sphere_forward} -surf {right_revfor_base_sphere}")
    run_logged(f"wb_command -surface-average {left_avgfor_cpgrid_sphere} -surf {left_cpgrid_sphere_forward} -surf {left_revfor_cpgrid_sphere}")
    run_logged(f"wb_command -surface-average {right_avgfor_cpgrid_sphere} -surf {right_cpgrid_sphere_forward} -surf {right_revfor_cpgrid_sphere}")
    run_logged(f"wb_command -surface-average {left_avgfor_anatgrid_sphere} -surf {left_anatgrid_sphere_forward} -surf {left_revfor_anatgrid_sphere}")
    run_logged(f"wb_command -surface-average {right_avgfor_anatgrid_sphere} -surf {right_anatgrid_sphere_forward} -surf {right_revfor_anatgrid_sphere}")

    # -------------------------
    # Recenter spheres
    # -------------------------
    print("\n[STEP] Recentering avgfor spheres")

    run_logged(f"wb_command -surface-modify-sphere -recenter {left_avgfor_base_sphere} 100 {left_avgfor_base_sphere}")
    run_logged(f"wb_command -surface-modify-sphere -recenter {right_avgfor_base_sphere} 100 {right_avgfor_base_sphere}")
    run_logged(f"wb_command -surface-modify-sphere -recenter {left_avgfor_cpgrid_sphere} 100 {left_avgfor_cpgrid_sphere}")
    run_logged(f"wb_command -surface-modify-sphere -recenter {right_avgfor_cpgrid_sphere} 100 {right_avgfor_cpgrid_sphere}")
    run_logged(f"wb_command -surface-modify-sphere -recenter {left_avgfor_anatgrid_sphere} 100 {left_avgfor_anatgrid_sphere}")
    run_logged(f"wb_command -surface-modify-sphere -recenter {right_avgfor_anatgrid_sphere} 100 {right_avgfor_anatgrid_sphere}")

    # -------------------------
    # Generate anatomical surfaces
    # -------------------------
    print("\n[STEP] Generating anatomical surfaces")

    run_logged(f"wb_command -surface-resample {left_older_anatomical_surface_cpgrid} {max_cp} {left_avgfor_cpgrid_sphere} \"BARYCENTRIC\" {left_avgfor_cpgrid_anat}")
    run_logged(f"wb_command -surface-resample {right_older_anatomical_surface_cpgrid} {max_cp} {right_avgfor_cpgrid_sphere} \"BARYCENTRIC\" {right_avgfor_cpgrid_anat}")
    run_logged(f"wb_command -surface-resample {left_older_anatomical_surface_anatgrid} {max_anat} {left_avgfor_anatgrid_sphere} \"BARYCENTRIC\" {left_avgfor_anatgrid_anat}")
    run_logged(f"wb_command -surface-resample {right_older_anatomical_surface_anatgrid} {max_anat} {right_avgfor_anatgrid_sphere} \"BARYCENTRIC\" {right_avgfor_anatgrid_anat}")

    # -------------------------
    # Generate revfor surfdist
    # -------------------------
    print("\n[STEP] Generating revfor surface distance maps")

    run_logged(f"wb_command -metric-math 'X*-1' {left_revfor_cpgrid_surfdist} -var X {left_cpgrid_surfdist_reverse}")
    run_logged(f"wb_command -metric-math 'X*-1' {left_revfor_anatgrid_surfdist} -var X {left_anatgrid_surfdist_reverse}")
    run_logged(f"wb_command -metric-math 'X*-1' {right_revfor_cpgrid_surfdist} -var X {right_cpgrid_surfdist_reverse}")
    run_logged(f"wb_command -metric-math 'X*-1' {right_revfor_anatgrid_surfdist} -var X {right_anatgrid_surfdist_reverse}")

    # -------------------------
    # Average surfdist
    # -------------------------
    print("\n[STEP] Computing average surface distance maps")

    run_logged(f"wb_command -metric-math '(J1+J2)/2' {left_avgfor_cpgrid_surfdist} -var J1 {left_revfor_cpgrid_surfdist} -var J2 {left_cpgrid_surfdist_forward}")
    run_logged(f"wb_command -metric-math '(J1+J2)/2' {left_avgfor_anatgrid_surfdist} -var J1 {left_revfor_anatgrid_surfdist} -var J2 {left_anatgrid_surfdist_forward}")
    run_logged(f"wb_command -metric-math '(J1+J2)/2' {right_avgfor_cpgrid_surfdist} -var J1 {right_revfor_cpgrid_surfdist} -var J2 {right_cpgrid_surfdist_forward}")
    run_logged(f"wb_command -metric-math '(J1+J2)/2' {right_avgfor_anatgrid_surfdist} -var J1 {right_revfor_anatgrid_surfdist} -var J2 {right_anatgrid_surfdist_forward}")

    run_logged(f"wb_command -set-structure {left_avgfor_cpgrid_surfdist} CORTEX_LEFT")
    run_logged(f"wb_command -set-structure {left_avgfor_anatgrid_surfdist} CORTEX_LEFT")
    run_logged(f"wb_command -set-structure {right_avgfor_cpgrid_surfdist} CORTEX_RIGHT")
    run_logged(f"wb_command -set-structure {right_avgfor_anatgrid_surfdist} CORTEX_RIGHT")

    print("\n[COMPLETE] Average map generation finished\n")