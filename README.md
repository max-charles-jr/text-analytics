# CLD-410 Text Analytics Assignment

Django app that reads novels from an encrypted S3 bucket, converts each to
an MP3 via AWS Polly, and displays NLTK token/named-entity frequency counts
at runtime.

## What's already provisioned (via CloudFormation, in account 638039899567 / us-east-1)

Stack `cld410-text-analytics` (`infra/platform.yaml`), deployed with
`NameSuffix=cld-mc-ta`:

| Resource | Name / ID |
|---|---|
| S3 bucket (SSE-KMS, versioned, public access blocked, deny-insecure-transport policy) | `tesu-cld410-text-analytics-mcharlescld-mc-ta` |
| KMS CMK | `alias/cld410-text-analyticscld-mc-ta` |
| IAM group ("group X") | `TextAnalyticsRWcld-mc-ta` (read/write on the bucket; `mcharles` is a member) |
| IAM policy attached to the group | `TextAnalyticsBucketReadWritecld-mc-ta` |
| ECS task role (S3 + KMS + Polly) | `cld-mc-ta-task-role` |
| ECS execution role | `cld-mc-ta-execution-role` |
| ECR repository (shared, not part of the stack -- see `infra/platform.yaml` header) | `638039899567.dkr.ecr.us-east-1.amazonaws.com/cld410-textlab` |
| ECS cluster | `cld410-textlab-clustercld-mc-ta` (Fargate) |
| CloudWatch log group | `/ecs/cld410-textlabcld-mc-ta` |
| ALB | `cld-mc-ta-alb` (security group `sg-03aa07c4ebc9becc5`, port 80) |
| Target group | `cld-mc-ta-tg` (port 8000, health check `/health`) |
| ECS task security group | `sg-0d977e6a52d65ca72` (port 8000 from the ALB only) |

Amazon Polly needs no resource of its own -- it's an API-only service. The
task role's `TextAnalyticsAppRuntimecld-mc-ta` policy already grants
`polly:SynthesizeSpeech`.

A prior iteration of this environment was provisioned imperatively via the
AWS CLI with unsuffixed names; its S3 bucket and ECS cluster have since
been deleted in favor of the CloudFormation stack above. A few unsuffixed
IAM/KMS objects from that era (`TextAnalyticsRW`, `TextAnalyticsBucketReadWrite`,
`TextAnalyticsAppRuntime`, `cld410-textlab-task-role`/`-execution-role`,
`alias/cld410-text-analytics`) are still in the account as harmless orphans.

## What's left to do manually

1. **Download 10 novels** from Project Gutenberg (Plain Text UTF-8) into `novels/`,
   named after their titles. For each book: go to
   `https://www.gutenberg.org/ebooks/<id>`, find "Download This eBook", click
   "Plain Text UTF-8" (not HTML/EPUB), and rename the saved file to the title.

   | Title | Gutenberg ID | Suggested filename |
   |---|---|---|
   | Pride and Prejudice (Jane Austen) | 1342 | `pride-and-prejudice.txt` |
   | Frankenstein (Mary Shelley) | 84 | `frankenstein.txt` |
   | Moby-Dick (Herman Melville) | 2701 | `moby-dick.txt` |
   | Dracula (Bram Stoker) | 345 | `dracula.txt` |
   | Alice's Adventures in Wonderland (Lewis Carroll) | 11 | `alice-in-wonderland.txt` |
   | The Adventures of Sherlock Holmes (A. C. Doyle) | 1661 | `sherlock-holmes.txt` |
   | The Picture of Dorian Gray (Oscar Wilde) | 174 | `dorian-gray.txt` |
   | A Tale of Two Cities (Charles Dickens) | 98 | `a-tale-of-two-cities.txt` |
   | The War of the Worlds (H. G. Wells) | 36 | `war-of-the-worlds.txt` |
   | War and Peace (Leo Tolstoy) | 2600 | `war-and-peace.txt` |

   It's fine to leave Gutenberg's standard license header/footer text in each
   file -- a few hundred words against a whole novel won't meaningfully skew
   the token/entity counts.
2. **Upload them to S3** (from a terminal with the AWS CLI configured):
   ```
   aws s3 sync novels/ s3://tesu-cld410-text-analytics-mcharlescld-mc-ta/raw/ --exclude "*" --include "*.txt"
   ```
3. **Build, push, and deploy** the Django app (needs Docker Desktop):
   ```
   ./infra/deploy.sh
   ```
   This builds the image, pushes it to ECR, registers a task definition, and
   creates (or updates) the ECS service behind the ALB. It prints the ALB's
   public DNS name at the end -- that URL is the running app.
4. **Take screenshots** for the SWDD: the S3 bucket properties (encryption,
   versioning, public access block) in the console, the IAM group membership
   and policy, the `/raw` and `/audio` directory listings, the ECS
   service/task running, and the Django dashboard itself showing conversion
   status plus the token/entity tables.

## Running locally (optional, for development)

```
cd app
pip install -r requirements.txt
python manage.py runserver
```
Requires AWS credentials in your environment (`aws configure`) with access
to the bucket above, since the app talks to S3 and Polly directly even when
run locally.

## Project layout

```
app/                  Django project (see app/README below via code comments)
  textlab/            project settings/urls/wsgi
  novels/             the one app: views, services (S3, Polly, NLTK), templates
infra/
  platform.yaml              CloudFormation template (IaC) for the S3/KMS/IAM/ECS/ALB
                              platform described in the table above. See the header
                              comments in the file for what it deliberately leaves out
                              (the ECR repo, the ECS TaskDefinition/Service, and the SSM
                              secret) and why.
  task-def.template.json   ECS task definition template (image filled in at deploy time)
  deploy.sh                 build -> push -> register task def -> create/update service
novels/               put your 10 downloaded .txt files here before syncing to S3
docs/                 SWDD and supporting material
