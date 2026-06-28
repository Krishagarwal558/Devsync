# Demo Script

## Goal

Show DevSync syncing a folder between two devices/folders.

## Setup

1. Start backend.
2. Run migrations.
3. Start desktop app on Device A.
4. Start desktop app on Device B.
5. Log in with the same account.
6. Select the same workspace.
7. Select different local folders.
8. Start sync on both.

## Demo

1. On Device A, create `hello.txt`.
2. Wait for upload.
3. Confirm `hello.txt` appears on Device B.
4. Edit `hello.txt` on Device B.
5. Confirm update appears on Device A.
6. Stop backend briefly, edit a file, start backend, click `Retry queued`.
7. Create a conflict by editing the same file on both sides.
8. Show `LOCAL-CONFLICT` and `REMOTE-CONFLICT`.
9. Export debug logs.

