<!-- Spec file for PLUTO vProctor. Section numbers (2B, 5.3, ...) refer to the files in docs/spec/. -->

## 1. Product summary

PLUTO vProctor is a local, privacy-friendly AI mock-interview and proctoring web app.

1. The candidate selects a job role or company and uploads a resume (PDF/DOCX).
2. The system parses skills, experience and education, and scores the resume against the job profile.
3. If the resume fails the job requirements, the candidate is marked **"Rejected at screening"** but is **still allowed to take the interview**.
4. The system filters the question dataset using the job profile plus resume, and asks only the necessary questions.
5. An AI interviewer shows each question on screen and speaks it aloud. The candidate sees their own live video and must sit at a proper distance (desktop/laptop webcam).
6. During the interview the system checks eye contact and body movement live. If the candidate looks away, an on-screen alert is shown, and score is deducted for looking away and for excessive movement.
7. The whole interview is recorded. Afterwards, **video analysis and audio analysis run simultaneously (in parallel)**.
8. Audio is checked for pauses and filler words ("umm", "ahh", "uh", "like", "you know"); a confidence score is computed and points are deducted.
9. At the end the candidate gets a score summary, what to improve, and a **timeline of every deduction with its mm:ss position in the recording**, clickable to seek the video.
