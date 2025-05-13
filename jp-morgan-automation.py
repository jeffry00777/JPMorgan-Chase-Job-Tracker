import requests
from datetime import datetime, timedelta
from email.message import EmailMessage
import smtplib
import os

# ---------- CONFIG ----------
EMAIL_SENDER = "stiffler00777@gmail.com"
EMAIL_PASSWORD = "********************"  
EMAIL_RECEIVER = "jeffrylivingston5@gmail.com"
SEEN_JOBS_FILE = "seen_jobs_jpmorgan.txt"
BASE_API = "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
KEYWORD = "Software"
LOCATION_ID = "300000000289738"
DAYS_LOOKBACK = 7
LIMIT = 100
# ----------------------------

CUTOFF_DATE = datetime.now() - timedelta(days=DAYS_LOOKBACK)

def build_url(offset):
    return (
        f"{BASE_API}?onlyData=true&expand=requisitionList.workLocation,"
        f"requisitionList.otherWorkLocations,requisitionList.secondaryLocations,"
        f"flexFieldsFacet.values,requisitionList.requisitionFlexFields&"
        f"finder=findReqs;siteNumber=CX_1001,facetsList=LOCATIONS%3BWORK_LOCATIONS%3B"
        f"WORKPLACE_TYPES%3BTITLES%3BCATEGORIES%3BORGANIZATIONS%3BPOSTING_DATES%3BFLEX_FIELDS,"
        f"limit={LIMIT},keyword=%22{KEYWORD}%22,locationId={LOCATION_ID},sortBy=RELEVANCY"
        f"{f',offset={offset}' if offset else ''}"
    )

def load_seen_jobs():
    seen = {}
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            for line in f:
                parts = line.strip().split("|||")
                if len(parts) == 4:
                    title, url, posted_date, status = parts
                elif len(parts) == 3:
                    title, url, posted_date = parts
                    status = "Pending"
                else:
                    continue
                seen[title] = (url, posted_date, status)
    return seen


def save_seen_jobs(jobs):
    with open(SEEN_JOBS_FILE, "w") as f:
        for title, (url, posted_date, status) in jobs.items():
            f.write(f"{title}|||{url}|||{posted_date}|||{status}\n")

def send_email_notification(jobs):
    if not jobs:
        return

    # Sort jobs by posted date DESC
    jobs.sort(key=lambda x: x["Posted Date"], reverse=True)

    msg = EmailMessage()
    msg["Subject"] = "🆕 JP Morgan Jobs - Posted in Last 7 Days"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    body = "New JP Morgan jobs posted within the last 7 days:\n\n"
    for job in jobs:
        body += f"- {job['Title']} | {job['Location']} | {job['Posted Date']}\n  {job['URL']}\n\n"

    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
        smtp.send_message(msg)


def fetch_recent_jobs():
    offset = 0
    all_jobs = []

    while True:
        url = build_url(offset)
        resp = requests.get(url, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])

        for job_item in items:
            for job in job_item.get("requisitionList", []):
                posted_date = job.get("PostedDate")
                if not posted_date:
                    continue

                post_date = datetime.strptime(posted_date, "%Y-%m-%d")
                if post_date >= CUTOFF_DATE:
                    job_id = job["Id"]
                    title = job["Title"]
                    location = job.get("PrimaryLocation", "N/A")
                    url = (
                        f"https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/"
                        f"jobs/preview/{job_id}/?keyword={KEYWORD}&location=United+States&locationId={LOCATION_ID}"
                        f"&locationLevel=country&mode=location"
                    )
                    key = f"{title} | {location} | {url}"
                    all_jobs.append({
                        "key": key,
                        "Title": title,
                        "Location": location,
                        "Posted Date": post_date.strftime("%Y-%m-%d"),
                        "URL": url
                    })

        if not data.get("hasMore"):
            break
        offset += LIMIT

    return all_jobs

def main():
    print("Fetching JP Morgan job listings...")
    recent_jobs = fetch_recent_jobs()
    seen_jobs = load_seen_jobs()
    new_jobs = []

    for job in recent_jobs:
        key = job["key"]
        posted_date = job["Posted Date"]
        url = job["URL"]

        if key not in seen_jobs:
            new_jobs.append(job)
        else:
            old_url, old_posted_date, old_status = seen_jobs[key]
            if posted_date != old_posted_date:
                new_jobs.append(job)

    if new_jobs:
        print(f"Sending {len(new_jobs)} new or updated job(s)...")
        send_email_notification(new_jobs)

        for job in recent_jobs:
            key = job["key"]
            status = seen_jobs[key][2] if key in seen_jobs else "Pending"
            seen_jobs[key] = (job["URL"], job["Posted Date"], status)

        save_seen_jobs(seen_jobs)
    else:
        print("No new or updated JP Morgan jobs found in the last 7 days.")


if __name__ == "__main__":
    main()
