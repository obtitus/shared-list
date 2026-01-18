To deploy, don't continue if you are in-doubt or if steps are not working out. Failing to deploy is also a success.
* Check that progress.md is up-to-date, reflecting the current project status where:
 [x] tasks are implemented and tested
 while [ ] are not implemented (Remining todo items are ok, but check that the functionality is indeed missing, or if the progress.md is just outdated).
* Check if `git status` is clean, with no modified or untracked files. If this is not the case, ask the user to fix.
* Check if `make lint test` is clean and all tests pass without warnings. If this is not the case, abort the deploy task and go into planning mode to debug the issue.
* Review `git --no-pager log`, unless the last commit updated the version number, increment the patch version (last digit) in `pyproject.toml`. Use `git --no-pager diff` when reviewing.
- run `uv sync`, ensure `uv.lock` updates to reflect the new version.
-  commit the change
- tag the commit with the same version number
- ensure your commit _only_ impacted the version.
* `git push`, you may need `git push -f`, but ask the user first.
* Check that the user is happy, if not, congratulations you can abort now!
* Ensure `make deploy` runs succesfully.