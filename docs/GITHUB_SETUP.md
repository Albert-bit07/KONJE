# Publishing KONJE privately from Windows

The authenticated GitHub connector available to the assistant can read/update existing repositories, but does **not** offer a repository-creation operation in this session. This source bundle contains a local Git repository bootstrap path, not a remotely created repository.

1. Extract `KONJE-github-source.zip` on your Windows laptop, and review the source. If merging into `C:\Users\alber\KONJE`, **back up any existing files first**. Your existing Git-ignored `reference/see-through` directory should stay on your laptop, outside the new GitHub commit.
2. Install Git for Windows and GitHub CLI if missing; in PowerShell run `gh auth login`.
3. Open PowerShell in the intended KONJE source root. Review `scripts/publish-private.ps1` and run `powershell -ExecutionPolicy Bypass -File scripts/publish-private.ps1`. It stages only source/docs/CI allowlisted paths, displays a file list, requires you to type `YES`, creates `Albert-bit07/KONJE` **private**, then pushes.
4. If you prefer manual setup, create a **private empty** `KONJE` repository at `https://github.com/new` (do not pre-create a README). Stage/commit only the source files, then `git remote add origin https://github.com/Albert-bit07/KONJE.git` and `git push -u origin main`.
5. Verify GitHub visibility reads **Private** and no model weights, real identities/photos, database files or keys were uploaded.

Do not publish this research prototype publicly until See Through contributor rights, chosen model licensing and volunteer privacy considerations are reviewed.