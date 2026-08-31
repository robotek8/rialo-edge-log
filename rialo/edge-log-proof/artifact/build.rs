fn main() {
    rialo_build_lib::build_script::setup_polkavm_artifact_build()
        .program_path("..")
        .run()
        .expect("failed to build Rialo PolkaVM artifact");
}

