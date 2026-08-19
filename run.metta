!(import! &self (library lib_import))

; These repositories are baked into the image before runtime. In PeTTa,
; git-import! also registers an existing repository as a library path; because
; the directories already exist, these calls do not clone or update anything.
!(git-import! "https://github.com/asi-alliance/OmegaClaw-Core.git")
!(git-import! "https://github.com/PaulTiffany/AlphaClaw.git")

!(import! &self (library OmegaClaw-Core lib_omegaclaw))
!(import! &self (library AlphaClaw alphaclaw))

!(omegaclaw)
