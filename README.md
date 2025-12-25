# Sudoku Image Generator

This worker generates Sudoku images, including both the solution and the puzzle itself.

It is intended to run inside a Kubernetes cluster with KEDA.

The worker will:
- Pull messages from Kafka
- Retrieve puzzle data from MongoDB
- Generate two images: the Sudoku solution and the puzzle
- Upload the generated images to S3 or S3-compatible storage like minio

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
  --puzzle-id pz-001 --puzzle-size 4 --level EASY --status GENERATING_IMAGE \
  --solution "1,2,3,4,3,4,1,2,2,1,4,3,4,3,2,1" \
  --puzzle "0,2,0,4,3,0,1,0,0,1,0,3,4,0,2,0"
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
