TripPulse

A serverless community safety check-in app, built entirely on AWS.

TripPulse lets someone start a trip and set a time they expect to arrive. If they don't check in as "arrived" by that time, the system notices on its own and automatically emails their trusted contact to say something might be wrong — no person has to click a button to make that happen.

Built as a solo AWS Cloud Computing elective project at WeThinkCode_.

1. The problem this solves

Think about walking home alone at night, taking a taxi somewhere unfamiliar, or a friend traveling solo between cities. If something goes wrong, there's often no automatic way for anyone to find out — someone would have to actively worry and check up on them.

TripPulse fixes that gap. You tell it "I expect to arrive by 8pm." If 8pm comes and goes and you haven't checked in, TripPulse notices by itself and alerts your emergency contact — without you or anyone else having to do anything.

2. How it works, in plain English
You start a trip — you give your name, your contact's name and email, and when you expect to arrive.
If you arrive safely, you check in, and the trip is marked complete.
Every 5 minutes, in the background, TripPulse automatically checks every trip that hasn't been checked in yet.
If a trip's expected arrival time has passed and nobody checked in, TripPulse sends an email alert to that trip's emergency contact, on its own.

That last step is the important one. Most simple apps only do something when a person clicks a button. TripPulse does something because time passed — nobody has to trigger it. That's what makes it a genuinely "cloud-native," event-driven system, not just a basic CRUD app.

3. Architecture — how the pieces connect
                POST /trips
                     │
                     ▼
              ┌─────────────┐
Client ──────▶│ API Gateway │   (the "front door" — receives requests)
              └─────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   createTrip     getTrip      checkIn
   (Lambda)       (Lambda)     (Lambda)
        │            │            │
        └────────────┼────────────┘
                     ▼
              ┌─────────────┐
              │  DynamoDB   │   (the database — stores every trip)
              │   (Trips)   │
              └─────────────┘
                     ▲
                     │ scanned every 5 minutes
              ┌──────────────────┐
              │  EventBridge     │   (the "timer" — runs on a schedule,
              │  Schedule        │    not because a user asked)
              └──────────────────┘
                     │
                     ▼
           ┌────────────────────┐
           │ checkOverdueTrips  │   (checks for late trips)
           │     (Lambda)       │
           └────────────────────┘
                     │
                     ▼
              ┌─────────────┐
              │     SNS     │──────▶ Email alert sent to
              │   (Topic)   │        the trusted contact
              └─────────────┘

In short: a client (like a phone app, or in this project's case, Postman for testing) talks to API Gateway. API Gateway hands the request to the right Lambda function. Each Lambda function reads or writes to the DynamoDB table. Separately, on a timer, EventBridge wakes up one more Lambda function every 5 minutes to check for anyone overdue, and that function tells SNS to send an email if needed.

4. AWS services used, and what each one actually does
Service	What it's for, in plain terms
API Gateway	The "receptionist" — takes incoming web requests and routes them to the right function. This is what turns a Lambda function into something a real app or website could call.
AWS Lambda	Small pieces of code that run only when needed, and only for as long as needed. No server sits running 24/7 — AWS spins each function up, runs it, and shuts it down again. Written in Python 3.12 here.
DynamoDB	A database that stores each trip as a simple record (like a row in a spreadsheet), without needing to manage database servers.
Amazon SNS	A notification service — it's the part that actually sends the email alert. You give it a message, and it delivers it to whoever's subscribed.
Amazon EventBridge (Scheduler)	A timer built into AWS. Instead of a person clicking "check now," this automatically triggers a function on a schedule — every 5 minutes, in this project.
IAM	Controls what each part of the system is allowed to do. For example, the createTrip function has permission to write to DynamoDB, but not to send emails — each function only gets the access it actually needs.
5. What a "trip" looks like in the database

Each trip is stored as one record in the Trips table, with these fields:

Field	Type	What it means
tripId	String	A unique ID for this trip, generated automatically
userName	String	Who's traveling
contactName	String	Who should be alerted if something's wrong
contactPhoneOrEmail	String	How to describe reaching that contact (shown in the alert)
startTime	String	The exact moment the trip was created
expectedArrivalTime	String	When the traveler expects to arrive
status	String	One of: in_progress (still traveling), arrived (checked in safely), or alert_sent (overdue, alert was sent)
6. The three main API endpoints

Base web address for all of these:

https://gzxb6hjpsf.execute-api.eu-north-1.amazonaws.com/prod
Start a trip — POST /trips

You send this when someone begins traveling.

What you send:

json
{
  "userName": "Nhlanhla",
  "contactName": "Mom",
  "contactPhoneOrEmail": "mom@example.com",
  "expectedArrivalTime": "2026-08-16T20:00:00"
}

What you get back:

json
{
  "message": "Trip started successfully",
  "tripId": "30b53297-4aab-4a05-956c-097638ba647c"
}
Check a trip's status — GET /trips/{tripId}

You send this when you want to see a trip's current details — useful for checking if it's still in progress, or already resolved.

What you get back:

json
{
  "tripId": "30b53297-4aab-4a05-956c-097638ba647c",
  "userName": "Nhlanhla",
  "contactName": "Mom",
  "contactPhoneOrEmail": "mom@example.com",
  "startTime": "2026-08-16T16:58:37.046043",
  "expectedArrivalTime": "2026-08-16T20:00:00",
  "status": "in_progress"
}
Check in safely — PATCH /trips/{tripId}

You send this when the traveler has arrived safely — it marks the trip as complete so no alert gets sent later.

What you get back:

json
{
  "message": "Checked in successfully",
  "tripId": "30b53297-4aab-4a05-956c-097638ba647c"
}
7. The automatic alert — how it runs without anyone asking

This is the part that makes TripPulse more than a basic app, so it's worth explaining clearly.

There's a fourth function, checkOverdueTrips, but unlike the three above, nobody calls it directly. Instead:

Every 5 minutes, EventBridge wakes it up automatically, all on its own.
The function looks through every trip still marked in_progress.
For each one, it compares the current time to that trip's expectedArrivalTime.
If the expected time has already passed, the function:
Updates that trip's status to alert_sent (so it won't alert twice)
Sends a message to SNS, which emails the trusted contact automatically

This was tested for real, not just assumed to work: a trip was created through the live API with an arrival time already in the past. Without touching anything else, an alert email genuinely arrived in the subscribed inbox within 5 minutes — proving the whole chain works automatically, start to finish.

8. Project files
trippulse/
  └── lambda/
        ├── createTrip.py         → handles POST /trips
        ├── getTrip.py            → handles GET /trips/{tripId}
        ├── checkIn.py            → handles PATCH /trips/{tripId}
        └── checkOverdueTrips.py  → runs on a timer, sends alerts

Each file is a separate AWS Lambda function, deployed individually, each with only the permissions it actually needs.

9. What's built, and what could be added later

 Already working:

Creating, checking, and updating trips through a real, live API
Fully automated overdue detection — no manual triggering needed
Real email alerts, proven to work end-to-end
Each function has its own minimal, correctly scoped permissions

Ideas for the future, if extended:

User accounts / login (using AWS Cognito), so trips are tied to real users instead of open access
A simple website front-end, instead of testing through Postman
SMS alerts as well as email
Setting up all these AWS resources through code (Infrastructure as Code) instead of manually through the console
Author

Your verification code:

WTC-Q7K2LXJT
You Tube vodeo
https://youtu.be/2CDcPVhJ3Mg?si=_sSe-gJZfRv-ukvj
