# Task: rename fetch_rows to load_rows everywhere

Test command: uv run --offline pytest -q

## Step 1
grep for fetch_rows. Reply with the list of files and lines that mention it.

## Step 2
Edit every file from Step 1 so that fetch_rows is named load_rows: the definition, every call, and every import. Do not change anything else.

## Step 3
Run the test command. If it fails, read the failure, change the code, and run it again. Stop when it exits 0.

## Step 4
Reply with the files changed and the test output pasted verbatim.
