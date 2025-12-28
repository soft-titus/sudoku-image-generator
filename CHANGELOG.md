# Changelog


## 1.0.0 - 2025-12-25
- fix: pre-commit git hooks
- feat: Initial commit



## 1.1.0 - 2025-12-26
- Merge pull request #1 from soft-titus/dev
- feat: add producer
- fix: use proper logging for ingester
- fix: updated requirements.txt
- feat: Add ingester



## 1.1.1 - 2025-12-27
- Merge pull request #2 from soft-titus/dev
- fix: handling non-retriable scenario
- fix: should save solution and puzzle as 2D array instead of flat array
- fix: skip heartbeat messages
- fix: update .env.example, add S3_PROTOCOL env var



## 1.2.0 - 2025-12-28
- Merge pull request #3 from soft-titus/dev
- docs: Update README.md, make the sample call to ingester clearer
- feat: Implement upload to s3 / minio + update mongodb after successful image generation
- fix: add helper function to draw sudoku board and numbers with pillow



## 1.2.1 - 2025-12-28
- Merge pull request #5 from soft-titus/dev
- fix: move dependency not needed by consumer to requirements-local.txt, only needed for ingester and producer for local testing
- Merge pull request #4 from soft-titus/dev
- docs: Update README.md, added features section

