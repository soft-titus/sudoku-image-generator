# Sudoku Image Generator

This worker generates Sudoku images, including both the solution and the puzzle itself.

It is intended to run inside a Kubernetes cluster with KEDA.

The worker will:
- Pull messages from Kafka
- Retrieve puzzle data from MongoDB
- Generate two images: the Sudoku solution and the puzzle
- Upload the generated images to S3 or S3-compatible storage like minio

---

## Features
- Horizontally scalable with KEDA + Kafka
- Supports Sudoku sizes 4x4, 9x9, and 16x16
- Fully configurable image generation via environment variables
- Uploads generated images to AWS S3 or S3-compatible storage (e.g. MinIO)

---

## Requirements
- python 3.13
- Docker & Docker Compose (for local development)

---

## Setup

1. Clone the repository:

```bash
git clone https://github.com/soft-titus/sudoku-image-generator.git
cd sudoku-image-generator
```

2. Install dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

3. Install Git pre-commit hooks:

```bash
cp hooks/pre-commit .git/hooks/
```

4. Run the application locally with Docker:

```bash
docker compose build
docker compose up -d
```

5. Feed data to MongoDB:

```bash
docker compose run --rm ingester \
  --puzzle-id pz-001 \
  --puzzle-size 4 \
  --level HARD \
  --status GENERATING_IMAGE \
  --solution \
"2,1,4,3\
,3,4,2,1\
,1,2,3,4\
,4,3,1,2" \
  --puzzle \
"0,0,0,0\
,3,0,0,0\
,1,2,3,0\
,0,0,0,2"

docker compose run --rm ingester \
  --puzzle-id pz-002 \
  --puzzle-size 9 \
  --level HARD \
  --status GENERATING_IMAGE \
  --solution \
"8,5,6,1,3,9,4,2,7\
,4,2,7,5,6,8,9,1,3\
,3,9,1,4,7,2,6,5,8\
,5,4,9,2,1,3,7,8,6\
,6,1,8,9,4,7,2,3,5\
,2,7,3,6,8,5,1,4,9\
,9,6,2,8,5,1,3,7,4\
,7,8,4,3,2,6,5,9,1\
,1,3,5,7,9,4,8,6,2" \
  --puzzle \
"8,5,0,0,0,0,0,0,0\
,4,0,0,0,6,0,9,0,3\
,0,0,1,0,0,0,6,5,8\
,0,0,0,0,0,0,7,0,0\
,0,0,0,0,4,0,0,3,5\
,2,7,0,6,8,0,0,4,0\
,0,6,0,0,5,0,0,7,0\
,0,0,4,0,2,0,5,0,0\
,1,3,0,0,0,4,0,0,2"

docker compose run --rm ingester \
  --puzzle-id pz-003 \
  --puzzle-size 16 \
  --level HARD \
  --status GENERATING_IMAGE \
  --solution \
"13,15,16,8,6,10,12,11,4,1,9,7,5,14,3,2
,3,9,14,11,8,13,2,4,5,12,10,15,7,16,1,6\
,6,10,7,2,9,1,5,15,16,3,11,14,12,4,13,8\
,1,4,12,5,16,3,14,7,6,13,8,2,9,11,15,10\
,2,13,15,12,1,9,16,8,14,10,3,6,4,5,11,7\
,5,11,6,16,15,14,3,10,7,2,1,4,13,8,9,12\
,8,14,4,10,2,5,7,13,15,11,12,9,16,1,6,3\
,7,1,9,3,12,11,4,6,8,16,13,5,10,2,14,15\
,15,7,10,4,5,16,11,14,3,9,2,12,1,6,8,13\
,16,5,8,14,13,7,15,9,1,6,4,10,2,3,12,11\
,12,3,1,13,4,6,10,2,11,14,5,8,15,7,16,9\
,9,2,11,6,3,12,8,1,13,15,7,16,14,10,4,5\
,11,12,3,15,7,4,1,16,10,5,6,13,8,9,2,14\
,14,8,5,1,11,2,13,12,9,7,16,3,6,15,10,4\
,4,16,13,9,10,15,6,5,2,8,14,11,3,12,7,1\
,10,6,2,7,14,8,9,3,12,4,15,1,11,13,5,16" \
  --puzzle \
"0,0,0,0,0,0,0,0,4,1,9,0,5,14,3,0\
,0,0,0,11,8,0,0,4,0,12,0,0,0,16,1,6\
,0,0,7,2,9,0,0,15,16,0,0,14,0,4,0,8\
,1,4,0,0,16,0,0,0,6,0,0,0,0,11,15,0\
,2,13,15,0,0,0,16,8,14,10,0,0,0,5,0,0\
,5,11,6,16,15,14,3,10,0,0,0,0,0,8,0,12\
,8,0,4,10,2,0,7,13,0,0,0,0,0,1,0,0\
,0,0,9,3,0,0,0,0,8,0,0,5,10,2,0,0\
,0,0,0,0,5,16,0,0,0,9,0,12,0,6,8,0\
,16,0,8,14,0,0,15,9,0,6,4,0,0,0,12,11\
,0,0,0,0,0,6,10,0,11,14,0,8,0,0,0,0\
,9,0,0,0,3,12,0,0,13,0,7,16,14,0,4,0\
,11,12,3,0,0,4,0,16,0,0,6,13,8,0,0,0\
,0,0,0,1,0,2,0,12,0,0,16,3,0,15,0,0\
,4,16,13,0,0,15,0,0,2,8,14,0,0,0,0,1\
,10,0,0,0,14,0,0,3,0,4,15,0,11,13,0,16"
```

| Parameter   | Required | Notes |
|-------------|----------|-------|
| puzzle-id   | yes      | Any string value |
| puzzle-size | no       | Default 9, valid: 4 / 9 / 16 |
| level       | no       | Default "EASY", valid: "EASY" / "MEDIUM" / "HARD" |
| status      | no       | Default "GENERATING_IMAGE", must be "GENERATING_IMAGE" |
| solution    | no       | Sudoku solution; randomly generated if not provided    |
| puzzle      | no       | Sudoku puzzle; randomly generated if not provided      |

If solution and puzzle are provided, they must match the puzzle size, or the worker will consider the data invalid:
- puzzle-size 4, should have 16 numbers
- puzzle-size 9, should have 81 numbers
- puzzle-size 16, should have 256 numbers

6. Send Kafka messages:

```bash
docker compose run --rm producer --puzzle-id pz-001 --retry-count 0
```

| Parameter   | Required | Notes |
|-------------|----------|-------|
| puzzle-id   | yes      | Must exist in MongoDB or worker will fail |
| retry-count | no       | Default 0, must be less than TASK_MAX_RETRIES in `.env` |

---

## Check Worker Logs

```bash
docker compose logs consumer -f
```

---

## Code Formatting and Linting

```bash
python -m black --check .
python -m pylint /*.py
```

---

## GitHub Actions

- `ci.yaml` : Runs linting and tests on all branches and PRs
- `build-and-publish-branch-docker-image.yaml` : Builds Docker images for
  branches
- `build-and-publish-production-docker-image.yaml` : Builds production
  images on `main`

---

### Branch Builds

Branch-specific Docker images are built with timestamped tags.  

Example: `1.0.0-dev-1762431`

---

### Production Builds

Merges to `main` trigger a production Docker image build.  
Versioning follows semantic versioning based on commit messages:

- `BREAKING CHANGE:` : major version bump
- `feat:` : minor version bump
- `fix:` : patch version bump

Example: `1.0.0`
