# TravelOS — Step-by-Step Deployment Guide

Beginner-friendly checklist for deploying TravelOS to AWS.
Work top to bottom — every step depends on the one before it.

## Architecture

```
Your Users (Browser)
       │
       │  HTTPS 443 / HTTP 80
       ▼
  EC2 Instance (Ubuntu 24.04, t2.micro)
  ┌───────────────────────────────────────────────┐
  │  Nginx  (ports 80 + 443 on host)             │
  │    │  TLS terminated here via Let's Encrypt   │
  │    ▼  (internal Docker network only)          │
  │  Backend / Gunicorn      :8000                │
  │  Celery Worker                                │
  │  Celery Beat                                  │
  │  Redis                   :6379 (internal)     │
  │  Qdrant                  :6333 (internal)     │
  └───────────────────────────────────────────────┘
       │
       │  port 5432 (private — never public)
       ▼
  AWS RDS  (PostgreSQL 16)

  AWS Amplify  — hosts Next.js frontend separately
  AWS Secrets Manager  — stores all .env secrets
```

No ALB. Nginx on the EC2 instance handles TLS directly using a free
Let's Encrypt certificate. Add an ALB later when you need multi-instance
scaling or AWS WAF — not before.

---

## Phase 1 — Prerequisites (on your laptop)

- [ ] Install **AWS CLI v2** — download from aws.amazon.com/cli, then verify:
  ```bash
  aws --version
  ```

- [ ] Configure AWS CLI with your IAM credentials:
  ```bash
  aws configure
  # Access Key ID     → from IAM → Users → Security credentials → Create access key
  # Secret Access Key → shown once, copy it now
  # Default region    → e.g. us-east-1  (pick one, use it for everything)
  # Output format     → json
  ```

- [ ] Verify credentials work:
  ```bash
  aws sts get-caller-identity
  # Should print your account ID. Error = wrong credentials.
  ```

- [ ] Generate your JWT secret key and save it somewhere safe:
  ```bash
  # Windows PowerShell:
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

- [ ] Note down your **AWS region** (e.g. `us-east-1`). Every resource you create
  must be in the same region.

---

## Phase 2 — Note Your VPC and Subnet IDs

- [ ] Go to AWS Console → **VPC** → **Your VPCs** → find the row marked "Default"
  → copy the **VPC ID** (looks like `vpc-0abc1234`)

- [ ] Go to **Subnets** → filter by your VPC → pick any **two subnets in different
  Availability Zones** (e.g. `us-east-1a` and `us-east-1b`)
  → copy both **Subnet IDs**

  > You need two subnets only if you later add an ALB. For now just note them.

---

## Phase 3 — AWS Secrets Manager

Store every secret here so nothing sensitive ever lives in a file on disk.

- [ ] AWS Console → **Secrets Manager** → **Store a new secret**
  - Secret type: **Other type of secret**
  - Add every row below using **Add row**:

  | Key | Value |
  |-----|-------|
  | `GROQ_API_KEY` | your Groq key (`gsk_...`) |
  | `DATABASE_URL` | fill in after Phase 4 |
  | `REDIS_URL` | `redis://:YOURREDISPASSWORD@localhost:6379/0` |
  | `CELERY_BROKER_URL` | `redis://:YOURREDISPASSWORD@localhost:6379/0` |
  | `CELERY_RESULT_BACKEND` | `redis://:YOURREDISPASSWORD@localhost:6379/1` |
  | `QDRANT_API_KEY` | random string — `python -c "import secrets; print(secrets.token_hex(24))"` |
  | `LITEAPI_KEY` | your LiteAPI key |
  | `HOTELSNL_API_KEY` | your Hotels.nl key |
  | `FOURSQUARE_API_KEY` | your Foursquare key |
  | `TICKETMASTER_API_KEY` | your Ticketmaster key |
  | `EVENTBRITE_TOKEN` | your Eventbrite token |
  | `DUFFEL_API_KEY` | your Duffel live key (not sandbox) |
  | `UNSPLASH_ACCESS_KEY` | your Unsplash key |
  | `JWT_SECRET_KEY` | the 64-char hex string from Phase 1 |
  | `POSTGRES_PASSWORD` | strong password — same one you will use in DATABASE_URL |
  | `REDIS_PASSWORD` | strong password — same one in REDIS_URL above |
  | `CORS_ORIGINS` | fill in after Phase 8 (Amplify URL) |
  | `SENTRY_DSN` | your Sentry DSN, or leave blank |

  - Click **Next**
  - Secret name: `travelos/prod` — this exact name is used by `infra/fetch_secrets.sh`
  - Click through and **Store**

---

## Phase 4 — RDS (PostgreSQL Database)

- [ ] AWS Console → **RDS** → **Create database**

  | Setting | Value |
  |---------|-------|
  | Engine | PostgreSQL |
  | Engine version | **16** |
  | Template | Free tier |
  | DB instance identifier | `travelos-prod` |
  | Master username | `postgres` |
  | Master password | the `POSTGRES_PASSWORD` from Phase 3 |
  | DB instance class | `db.t3.micro` |
  | Storage | 20 GB gp2 |
  | **Public access** | **No** — critical |
  | VPC | your default VPC |
  | VPC security group | Create new → name it `travelos-rds-sg` |
  | Initial database name | `travelos` |

- [ ] Wait ~5 minutes for status to show **Available**

- [ ] Click your database → copy the **Endpoint** (looks like
  `travelos-prod.cxyz1234.us-east-1.rds.amazonaws.com`)

- [ ] Go back to Secrets Manager → `travelos/prod` → **Edit** → set `DATABASE_URL`:
  ```
  postgresql+asyncpg://postgres:YOURPASSWORD@travelos-prod.cxyz1234.us-east-1.rds.amazonaws.com:5432/travelos
  ```

---

## Phase 5 — Security Groups

Create these in AWS Console → **EC2** → **Security Groups** → **Create security group**.

### EC2 Security Group (`travelos-ec2-sg`)

- [ ] Create with these rules:

  | Direction | Protocol | Port | Source | Reason |
  |-----------|----------|------|--------|--------|
  | Inbound | TCP | 443 | 0.0.0.0/0 | HTTPS from internet |
  | Inbound | TCP | 80 | 0.0.0.0/0 | HTTP → redirected to HTTPS by Nginx |
  | Inbound | TCP | 22 | **My IP** | SSH — your laptop only |
  | Outbound | TCP | 443 | 0.0.0.0/0 | External APIs (Groq, Duffel, etc.) |
  | Outbound | TCP | 80 | 0.0.0.0/0 | Nominatim, Open-Meteo |
  | Outbound | TCP | 5432 | `travelos-rds-sg` | RDS Postgres |

  > For the last outbound rule: set Source/Destination type to "Custom" and type
  > `travelos-rds-sg` — AWS allows referencing another security group by name.

### RDS Security Group (`travelos-rds-sg`)

- [ ] Edit the group that was auto-created in Phase 4 — it starts empty.
  Add one inbound rule:

  | Direction | Protocol | Port | Source | Reason |
  |-----------|----------|------|--------|--------|
  | Inbound | TCP | 5432 | `travelos-ec2-sg` | DB access from EC2 only |

  > Nothing else. RDS is never directly reachable from the internet.

---

## Phase 6 — IAM Role for EC2

Lets the EC2 instance read from Secrets Manager without hardcoded AWS credentials.

- [ ] AWS Console → **IAM** → **Roles** → **Create role**
  - Trusted entity: **AWS service** → **EC2**
  - Attach policy: search `SecretsManagerReadWrite` → select it
  - Role name: `travelos-ec2-role`
  - Create role

---

## Phase 7 — EC2 Instance

### Launch

- [ ] AWS Console → **EC2** → **Launch instances**

  | Setting | Value |
  |---------|-------|
  | Name | `travelos-backend` |
  | AMI | **Ubuntu 24.04 LTS** |
  | Instance type | `t2.micro` |
  | Key pair | Create new → `travelos-key` → download `.pem` → **keep it safe** |
  | Network | your default VPC |
  | Subnet | any public subnet |
  | Auto-assign public IP | **Enable** |
  | Security group | existing → `travelos-ec2-sg` |
  | Storage | 20 GB gp3 |
  | IAM instance profile | `travelos-ec2-role` |

- [ ] Launch and copy the **Public IPv4 address** from the instance detail page

### SSH in

- [ ] Fix key permissions and connect (run on your laptop):
  ```bash
  # Windows PowerShell:
  icacls "C:\path\to\travelos-key.pem" /inheritance:r /grant:r "$env:USERNAME:(R)"

  ssh -i "C:\path\to\travelos-key.pem" ubuntu@YOUR-EC2-PUBLIC-IP
  ```

All commands from here run **on the EC2 instance**.

### Install Docker

- [ ]
  ```bash
  sudo apt-get update && sudo apt-get upgrade -y
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker ubuntu
  exit
  ```

- [ ] SSH back in, then verify Docker works without sudo:
  ```bash
  docker run hello-world
  ```

### Install AWS CLI

- [ ]
  ```bash
  sudo apt-get install -y awscli python3
  aws --version
  ```

### Clone the repo

- [ ]
  ```bash
  sudo mkdir -p /opt/TravelOS
  sudo chown ubuntu:ubuntu /opt/TravelOS
  git clone https://github.com/Mohak0140/TravelOS.git /opt/TravelOS
  cd /opt/TravelOS
  ```

  > Private repo? Use:
  > `git clone https://YOUR_GITHUB_TOKEN@github.com/Mohak0140/TravelOS.git /opt/TravelOS`

### Fetch secrets

- [ ]
  ```bash
  chmod +x infra/fetch_secrets.sh
  ./infra/fetch_secrets.sh travelos/prod
  ```

- [ ] Verify the file was written (do NOT cat it):
  ```bash
  ls -la .env
  wc -l .env
  # Should show at least 15 lines
  ```

---

## Phase 8 — SSL Certificate with Let's Encrypt

### Point your domain to EC2 first

- [ ] In your DNS provider add an **A record**:
  - Name: `api` (or your chosen subdomain)
  - Value: your EC2 Public IP

- [ ] Wait for DNS to propagate, then verify:
  ```bash
  nslookup api.yourdomain.com
  # Must return your EC2 IP before continuing
  ```

### Get the certificate

- [ ] Install Certbot:
  ```bash
  sudo apt-get install -y certbot
  ```

- [ ] Get the certificate (port 80 must be reachable — the stack does not need to be
  running yet, Certbot uses its own temporary server):
  ```bash
  sudo certbot certonly \
    --standalone \
    --non-interactive \
    --agree-tos \
    --email your@email.com \
    -d api.yourdomain.com
  ```

  Success output ends with:
  ```
  Certificate is saved at: /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem
  Key is saved at:         /etc/letsencrypt/live/api.yourdomain.com/privkey.pem
  ```

### Update nginx.conf with your domain

- [ ] On your **laptop**, edit `infra/nginx/nginx.conf` — replace both occurrences of
  `YOUR_DOMAIN` with your actual domain:
  ```nginx
  ssl_certificate     /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;
  ```

- [ ] Commit and push:
  ```bash
  git add infra/nginx/nginx.conf
  git commit -m "chore(infra): set SSL domain in nginx.conf"
  git push origin master
  ```

- [ ] Pull on EC2:
  ```bash
  cd /opt/TravelOS && git pull origin master
  ```

### Set up auto-renewal

- [ ] Certificates expire every 90 days. Add a cron job to renew automatically:
  ```bash
  sudo crontab -e
  ```
  Add this line:
  ```
  0 0,12 * * * certbot renew --quiet --deploy-hook "docker exec infra-nginx-1 nginx -s reload"
  ```

---

## Phase 9 — Build and Start the Stack

All commands from `/opt/TravelOS` on EC2.

- [ ] Build Docker images (takes 5–10 min first time):
  ```bash
  docker compose \
    -f infra/docker-compose.prod.yml \
    -f infra/docker-compose.aws-freetier.yml \
    build
  ```

- [ ] Start Redis and Qdrant first, wait for them to be healthy:
  ```bash
  docker compose \
    -f infra/docker-compose.prod.yml \
    -f infra/docker-compose.aws-freetier.yml \
    up -d redis qdrant

  # Wait ~10 seconds, then check:
  docker compose -f infra/docker-compose.prod.yml ps
  # Both should show (healthy)
  ```

- [ ] Run database migrations against RDS:
  ```bash
  docker compose \
    -f infra/docker-compose.prod.yml \
    -f infra/docker-compose.aws-freetier.yml \
    run --rm migrate
  ```
  Last line should be: `Running upgrade ... -> c7d8e9f0a1b2`
  If it errors, check that `DATABASE_URL` in `.env` matches your RDS endpoint
  and that the RDS security group allows traffic from this EC2.

- [ ] Start the full stack:
  ```bash
  docker compose \
    -f infra/docker-compose.prod.yml \
    -f infra/docker-compose.aws-freetier.yml \
    up -d
  ```

- [ ] Verify all services are running:
  ```bash
  docker compose -f infra/docker-compose.prod.yml ps
  ```
  Expected:
  ```
  infra-nginx-1          running    0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
  infra-backend-1        healthy
  infra-celery_worker-1  running
  infra-celery_beat-1    running
  infra-redis-1          healthy
  infra-qdrant-1         healthy
  ```

- [ ] Health check from EC2 itself:
  ```bash
  curl http://localhost/health
  # Expected: {"status":"ok","db":"connected","redis":"connected","qdrant":"connected"}
  ```

- [ ] Health check over HTTPS from your laptop:
  ```bash
  curl https://api.yourdomain.com/health
  # Same expected response
  ```

- [ ] Confirm HTTP redirects to HTTPS:
  ```bash
  curl -I http://api.yourdomain.com/health
  # Expected: 301 redirect to https://
  ```

---

## Phase 10 — Frontend on AWS Amplify

- [ ] AWS Console → **Amplify** → **New app** → **Host web app** → **GitHub**
  → authorize GitHub → select this repository → select branch `master`

- [ ] Amplify auto-detects `infra/amplify.yml`. No build settings to change.

- [ ] Go to **Environment variables** → **Add variable**:

  | Variable | Value |
  |----------|-------|
  | `NEXT_PUBLIC_API_URL` | `https://api.yourdomain.com` |

- [ ] Click **Save and deploy** — first deploy takes ~3–5 minutes

- [ ] Once done, copy your Amplify URL (e.g. `https://main.d1abc123.amplifyapp.com`)

- [ ] Update `CORS_ORIGINS` in Secrets Manager:
  ```
  ["https://main.d1abc123.amplifyapp.com"]
  ```

- [ ] Re-fetch secrets on EC2 and restart the backend:
  ```bash
  cd /opt/TravelOS
  ./infra/fetch_secrets.sh travelos/prod

  docker compose \
    -f infra/docker-compose.prod.yml \
    -f infra/docker-compose.aws-freetier.yml \
    restart backend
  ```

---

## Phase 11 — Auto-restart on Reboot

- [ ] Create a systemd service so the stack starts automatically if EC2 reboots:
  ```bash
  sudo nano /etc/systemd/system/travelos.service
  ```

  Paste:
  ```ini
  [Unit]
  Description=TravelOS Docker Compose Stack
  After=docker.service
  Requires=docker.service

  [Service]
  Type=oneshot
  RemainAfterExit=yes
  WorkingDirectory=/opt/TravelOS
  ExecStart=/usr/bin/docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.aws-freetier.yml up -d
  ExecStop=/usr/bin/docker compose -f infra/docker-compose.prod.yml -f infra/docker-compose.aws-freetier.yml down
  TimeoutStartSec=300

  [Install]
  WantedBy=multi-user.target
  ```

- [ ] Enable and start it:
  ```bash
  sudo systemctl enable travelos
  sudo systemctl start travelos
  ```

---

## Phase 12 — Smoke Tests

Run these in order. Stop and fix any failure before continuing.

- [ ] **Health check** (public HTTPS path):
  ```bash
  curl https://api.yourdomain.com/health
  # {"status":"ok","db":"connected","redis":"connected","qdrant":"connected"}
  ```

- [ ] **Register a user**:
  ```bash
  curl -X POST https://api.yourdomain.com/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"TestPass123!"}'
  # {"id":"...","email":"test@example.com"}
  ```

- [ ] **Login and check JWT**:
  ```bash
  curl -X POST https://api.yourdomain.com/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"TestPass123!"}'
  # {"access_token":"...","token_type":"bearer"}
  ```

- [ ] **Rate limiting** — run this 12 times quickly, the last few should return 429:
  ```bash
  for i in {1..12}; do
    curl -s -o /dev/null -w "%{http_code}\n" \
      -X POST https://api.yourdomain.com/auth/login \
      -H "Content-Type: application/json" \
      -d '{"email":"x@x.com","password":"wrong"}'
  done
  ```

- [ ] **Celery beat is running**:
  ```bash
  docker logs infra-celery_beat-1 2>&1 | tail -20
  # Should show "beat: Starting..." and periodic task schedules
  ```

- [ ] **In-browser tests** — open your Amplify URL and:
  - [ ] Register an account
  - [ ] Create a trip
  - [ ] Generate an itinerary (exercises the full multi-agent graph + Celery worker)
  - [ ] Chat with the concierge (exercises Qdrant)
  - [ ] Check hotels / flights / weather tabs (exercises provider API keys)

---

## Ongoing Operations

### Deploy a code update

```bash
cd /opt/TravelOS
git pull origin master

docker compose \
  -f infra/docker-compose.prod.yml \
  -f infra/docker-compose.aws-freetier.yml \
  build backend celery_worker celery_beat

docker compose \
  -f infra/docker-compose.prod.yml \
  -f infra/docker-compose.aws-freetier.yml \
  up -d --no-deps backend celery_worker celery_beat

# If you changed any database models:
docker compose \
  -f infra/docker-compose.prod.yml \
  -f infra/docker-compose.aws-freetier.yml \
  run --rm migrate
```

### Useful log commands

```bash
docker logs -f infra-backend-1          # API logs
docker logs -f infra-celery_worker-1    # Celery worker logs
docker logs -f infra-celery_beat-1      # Celery beat logs
docker compose -f infra/docker-compose.prod.yml logs -f   # all at once
```

### When to add an ALB later

Add it when you hit one of these:
- You want to run 2+ EC2 instances behind a load balancer
- You need AWS WAF for DDoS / bot protection
- You set up auto-scaling groups

Until then, Certbot + Nginx on a single EC2 is the right approach.

---

## Master Checklist (tick these off in order)

- [ ] Phase 1 — AWS CLI installed, `aws sts get-caller-identity` works, JWT secret generated
- [ ] Phase 2 — VPC ID and two subnet IDs noted
- [ ] Phase 3 — Secret `travelos/prod` created in Secrets Manager with all keys
- [ ] Phase 4 — RDS PostgreSQL 16 created; endpoint noted; `DATABASE_URL` updated in secret
- [ ] Phase 5 — `travelos-ec2-sg` and `travelos-rds-sg` created with correct rules
- [ ] Phase 6 — IAM role `travelos-ec2-role` created with Secrets Manager access
- [ ] Phase 7 — EC2 `t2.micro` Ubuntu 24.04 launched; Docker installed; repo cloned; `.env` written
- [ ] Phase 8 — Domain A record points to EC2; Let's Encrypt cert issued; `nginx.conf` updated with domain; auto-renewal cron added
- [ ] Phase 9 — Stack built; migrations ran; all services healthy; `curl https://api.yourdomain.com/health` returns ok
- [ ] Phase 10 — Amplify deployed; `NEXT_PUBLIC_API_URL` set; `CORS_ORIGINS` updated in secret; backend restarted
- [ ] Phase 11 — systemd service installed; stack survives `sudo reboot`
- [ ] Phase 12 — All smoke tests pass; in-browser trip generation works end to end
