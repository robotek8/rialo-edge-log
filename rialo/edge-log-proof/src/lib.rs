use rialo_venus_proc_macro::rialo;

rialo! {
    workflow {
        state {
            device_id: u64,
            public_key_fingerprint_0: u64,
            public_key_fingerprint_1: u64,
            public_key_fingerprint_2: u64,
            public_key_fingerprint_3: u64,
            batch_digest_0: u64,
            batch_digest_1: u64,
            batch_digest_2: u64,
            batch_digest_3: u64,
            first_sequence: u64,
            last_sequence: u64,
            reading_count: u64,
        }

        program {
            use rialo_s_program::{
                entrypoint::ProgramResult,
                msg,
            };

            initiating fn start(
                &mut self,
                device_id: u64,
                public_key_fingerprint_0: u64,
                public_key_fingerprint_1: u64,
                public_key_fingerprint_2: u64,
                public_key_fingerprint_3: u64,
                batch_digest_0: u64,
                batch_digest_1: u64,
                batch_digest_2: u64,
                batch_digest_3: u64,
                first_sequence: u64,
                last_sequence: u64,
                reading_count: u64,
            ) -> ProgramResult {
                self.device_id = device_id;
                self.public_key_fingerprint_0 = public_key_fingerprint_0;
                self.public_key_fingerprint_1 = public_key_fingerprint_1;
                self.public_key_fingerprint_2 = public_key_fingerprint_2;
                self.public_key_fingerprint_3 = public_key_fingerprint_3;
                self.batch_digest_0 = batch_digest_0;
                self.batch_digest_1 = batch_digest_1;
                self.batch_digest_2 = batch_digest_2;
                self.batch_digest_3 = batch_digest_3;
                self.first_sequence = first_sequence;
                self.last_sequence = last_sequence;
                self.reading_count = reading_count;

                msg!("Rialo Edge Log proof recorded");
                Ok(())
            }

            initiating fn register(
                &mut self,
                device_id: u64,
                public_key_fingerprint_0: u64,
                public_key_fingerprint_1: u64,
                public_key_fingerprint_2: u64,
                public_key_fingerprint_3: u64,
            ) -> ProgramResult {
                self.device_id = device_id;
                self.public_key_fingerprint_0 = public_key_fingerprint_0;
                self.public_key_fingerprint_1 = public_key_fingerprint_1;
                self.public_key_fingerprint_2 = public_key_fingerprint_2;
                self.public_key_fingerprint_3 = public_key_fingerprint_3;
                self.batch_digest_0 = 0;
                self.batch_digest_1 = 0;
                self.batch_digest_2 = 0;
                self.batch_digest_3 = 0;
                self.first_sequence = 0;
                self.last_sequence = 0;
                self.reading_count = 0;

                msg!("Rialo Edge Log device registered");
                Ok(())
            }
        }
    }
}
