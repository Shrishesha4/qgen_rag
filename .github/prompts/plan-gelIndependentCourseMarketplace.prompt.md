# Plan: GEL Independent Course Marketplace

Transform GEL from an internal learning tool into an independent platform where teachers create and sell courses, students browse/enroll, and an AI tutor assists in a split-pane learning interface.

## TL;DR

Build a course marketplace layer on top of existing subject/question infrastructure. Teachers create "Courses" (packaging subjects + custom content modules), set pricing, and publish. Students browse a catalog, enroll (free or paid), and learn through a resizable split-pane UI (content left, AI tutor right). The tutor gains new abilities: generate personalized tests and learning modules from predefined templates on demand.

---

## Phase 1: Data Model & Core Backend (Foundation)

**Goal**: Establish Course, Module, Enrollment, and Payment entities.

### Steps

1. **Create Course model** (`backend/app/models/course.py`)
   - Fields: `id`, `teacher_id`, `title`, `slug`, `description`, `cover_image_url`, `price_cents` (0 = free), `currency`, `status` (draft/published/archived), `is_featured`, `preview_video_url`, `learning_outcomes` (JSONB), `created_at`, `updated_at`
   - Relationship: `teacher` → User, `modules` → CourseModule[], `enrollments` → Enrollment[]

2. **Create CourseModule model**
   - Fields: `id`, `course_id`, `title`, `description`, `order_index`, `module_type` (content/quiz/assignment), `content_data` (JSONB — markdown, video URL, or template ref), `duration_minutes`, `is_preview` (free preview before enrollment)
   - Relationship: `course` → Course, `module_questions` → ModuleQuestion[] (for quiz type)

3. **Create ModuleQuestion join table**
   - Links approved questions from vquest DB to quiz modules
   - Fields: `module_id`, `question_id`, `sequence`, `weight`

4. **Create Enrollment model**
   - Fields: `id`, `student_id`, `course_id`, `enrolled_at`, `status` (active/completed/refunded), `progress_data` (JSONB — completed module IDs, scores), `completed_at`
   - Unique constraint: `(student_id, course_id)`

5. **Create Payment model** (if using internal ledger; or integrate Stripe later)
   - Fields: `id`, `enrollment_id`, `student_id`, `amount_cents`, `currency`, `status` (pending/completed/failed/refunded), `provider` (stripe/razorpay/manual), `provider_ref`, `created_at`

6. **Create PersonalizedItem model** (AI-generated tests/modules)
   - Fields: `id`, `student_id`, `course_id`, `item_type` (test/learning_module), `template_id`, `generated_content` (JSONB), `created_at`, `status` (draft/active/completed)

7. **Alembic migration** — single migration file with all tables, FK constraints, indexes

**Relevant files**
- Create: `backend/app/models/course.py`
- Create: `backend/app/models/enrollment.py`
- Create: `backend/app/models/payment.py`
- Create: `backend/app/models/personalized_item.py`
- Modify: `backend/app/models/__init__.py` — export new models
- Create: `backend/alembic/versions/xxx_add_course_marketplace.py`

---

## Phase 2: Course & Enrollment APIs

**Goal**: CRUD for courses/modules, enrollment flow, question fetching from vquest.

### Steps

1. **Course CRUD endpoints** (`backend/app/api/v1/endpoints/courses.py`)
   - `POST /courses` — teacher creates course (draft)
   - `GET /courses` — public catalog (published only, paginated, filterable by subject/price/rating)
   - `GET /courses/{slug}` — public course detail (with preview modules)
   - `PATCH /courses/{course_id}` — teacher updates own course
   - `POST /courses/{course_id}/publish` — transition draft → published (validates completeness)
   - `DELETE /courses/{course_id}` — soft-delete (archive)

2. **Module CRUD endpoints**
   - `POST /courses/{course_id}/modules` — add module
   - `PATCH /courses/{course_id}/modules/{module_id}` — update
   - `DELETE /courses/{course_id}/modules/{module_id}` — remove
   - `POST /courses/{course_id}/modules/{module_id}/reorder` — change sequence
   - `POST /courses/{course_id}/modules/{module_id}/questions` — attach approved questions (search vquest by subject/topic/difficulty)

3. **Question fetching service** (`backend/app/services/vquest_service.py`)
   - `get_approved_questions(subject_id, topic_id, filters)` — query Question table where `vetting_status = 'approved'`
   - `search_questions_for_module(query, subject_id, topic_id, difficulty, bloom_level, limit)` — semantic + filter search
   - Used by module question attachment

4. **Enrollment endpoints** (`backend/app/api/v1/endpoints/enrollments.py`)
   - `POST /courses/{course_id}/enroll` — create enrollment (free) or initiate payment (paid)
   - `GET /enrollments` — student's enrolled courses
   - `GET /enrollments/{enrollment_id}` — enrollment detail with progress
   - `PATCH /enrollments/{enrollment_id}/progress` — update progress (mark module complete)

5. **Payment webhook endpoint** (Phase 4 integration)
   - Placeholder: `POST /payments/webhook` — Stripe/Razorpay callback

**Relevant files**
- Create: `backend/app/api/v1/endpoints/courses.py`
- Create: `backend/app/api/v1/endpoints/enrollments.py`
- Create: `backend/app/services/vquest_service.py`
- Modify: `backend/app/api/v1/router.py` — register new routers
- Create: `backend/app/schemas/course.py`, `enrollment.py`

---

## Phase 3: Split-Pane Learning Frontend

**Goal**: Resizable two-pane UI — content browser (left) + stateful AI tutor (right).

### Steps

1. **Create enrolled course learning page** (`trainer-web/src/routes/student/learn/[courseSlug]/+page.svelte`)
   - Fetch enrollment + course modules on mount
   - Two-pane layout using a resizable splitter component
   - Left pane: Module list sidebar + content viewer (markdown/video)
   - Right pane: AI tutor chat (reuse existing train page chat components)
   - Persist pane widths in localStorage

2. **Module content viewer component** (`trainer-web/src/lib/components/ModuleViewer.svelte`)
   - Render markdown (existing MarkdownContent component)
   - Embed video player (if `module_type` has video URL)
   - Quiz renderer (if `module_type === 'quiz'` — fetch questions, render MCQ form)

3. **Resizable splitter component** (`trainer-web/src/lib/components/ResizableSplitter.svelte`)
   - Horizontal drag handle
   - Min/max width constraints (e.g., 300px min each pane)
   - Collapse buttons for mobile

4. **Integrate AI tutor in right pane**
   - Pass `course_id`, `module_id`, and student's **learning history summary** to tutor on each session open
   - Tutor system prompt includes: current module content, course learning outcomes, student's weak topics (derived from past attempt scores + reasoning quality), and topics already mastered (skip or advance faster)
   - Student can ask questions about current content, request explanations, or say "test me" / "make a learning module for X"
   - Session persists per course (extend `InquirySession` with `course_id`, `module_id`)
   - Tutor proactively surfaces weak areas: "I notice you've struggled with [topic] — want me to build a quick refresher?" based on history

5. **Progress tracking**
   - Mark module complete on "Next" or quiz submission
   - Update enrollment progress via API
   - Visual progress bar in sidebar

6. **Mobile responsive layout**
   - Stack panes vertically on small screens
   - Tab switcher: "Content" | "Tutor"

**Relevant files**
- Create: `trainer-web/src/routes/student/learn/[courseSlug]/+page.svelte`
- Create: `trainer-web/src/routes/student/learn/[courseSlug]/+page.ts` (load function)
- Create: `trainer-web/src/lib/components/ModuleViewer.svelte`
- Create: `trainer-web/src/lib/components/ResizableSplitter.svelte`
- Modify: `trainer-web/src/routes/student/train/+page.svelte` — extract chat components for reuse
- Create: `trainer-web/src/lib/components/TutorChat.svelte` (extracted)
- Create: `trainer-web/src/lib/api/courses.ts`, `enrollments.ts`

---

## Phase 4: AI Tutor Enhancements (History-Driven Personalized Tests & Modules)

**Goal**: Student can ask the tutor (or explicitly request) a one-time personalized test or custom learning module generated specifically from *their* learning history — weak topics, past mistakes, reasoning gaps — not a generic template fill-in.

### Step 1 — Learning History Aggregation Service

1. **`LearningHistoryService`** (`backend/app/services/learning_history_service.py`)
   - Inputs: `student_id`, `course_id` (optional)
   - Aggregates across:
     - `StudentAttempt` records → per-topic scores, reasoning quality, attempt counts
     - `InquirySession` records → level reached, turns completed, where student stalled
     - `Enrollment.progress_data` → which modules completed, quiz scores
   - Outputs a structured `LearningProfile`:
     ```json
     {
       "weak_topics": [{"topic_id": "...", "topic_name": "...", "avg_score": 0.42, "fail_count": 3}],
       "mastered_topics": [{"topic_id": "...", "topic_name": "...", "avg_score": 0.91}],
       "reasoning_gaps": ["confuses X with Y", "skips causal explanation"],
       "total_questions_seen": 48,
       "overall_level": "intermediate"
     }
     ```
   - Called at session open and before generation — always fresh, never cached more than 5 min

### Step 2 — Personalized One-Time Test Generation

2. **Endpoint**: `POST /tutor/generate-test`
   - Input: `course_id`, optional `topic_focus[]` override, `question_count` (default 10), `difficulty_bias` (auto / easy / hard)
   - Process:
     1. Call `LearningHistoryService` to get `LearningProfile`
     2. Select questions **weighted toward `weak_topics`** (70% from weak, 30% from rest) from approved vquest DB
     3. If insufficient approved questions for a weak topic → LLM generates the gap questions on the fly using topic syllabus as context
     4. Assemble into a one-time `PersonalizedItem` with `item_type = "test"` — **never reused**, each generation is unique
     5. Persist to DB, return item ID + full question set
   - The test is **one-time**: once submitted it becomes read-only history, a new request generates a new one

### Step 3 — Custom Learning Module Generation

3. **Endpoint**: `POST /tutor/generate-module`
   - Input: `course_id`, `topic_id` (the specific gap to address), optional `focus_areas[]` freetext
   - Process:
     1. Call `LearningHistoryService` — extract what the student got wrong and why (reasoning gaps)
     2. Fetch topic syllabus + approved questions for that topic as RAG context
     3. LLM generates a **bespoke module** using a structural template as scaffold:
        - `concept_recap` — targeted explanation of the exact concept the student missed, written at their level
        - `misconception_correction` — directly addresses the specific error pattern in their history
        - `worked_examples` — 2–3 examples tailored to their weak sub-area
        - `practice_problems` — 3–5 fresh problems (pulled from vquest + LLM-generated) on the gap area
        - `recap_summary` — 3-bullet consolidation
     4. Persist as `PersonalizedItem` with `item_type = "learning_module"`
   - Module is **one-time and custom** — not a reusable template instance, it's a generated document unique to this student at this moment

### Step 4 — Tutor Chat Intent Handling

4. **Intent detection in `_build_inquiry_system_prompt`**
   - Add a new mode: `personalization_intent`
   - Trigger phrases (fuzzy): "test me", "create a test", "quiz me on X", "I need practice", "build a module for Y", "I keep getting X wrong"
   - When detected: tutor responds with a confirmation message + calls generation endpoint in background → streams a rich card into the chat when ready
   - Tutor also **proactively suggests** when history shows 2+ failures on the same topic: "I noticed you've missed questions on [topic] a few times — want me to build a focused module for it?"

### Step 5 — Frontend Rendering

5. **`PersonalizedTestViewer.svelte`**
   - Renders generated test as interactive MCQ/short-answer quiz inline in the learning pane
   - Timer optional (set by generation params)
   - Submit → score displayed, wrong answers highlighted, correct reasoning shown
   - Results saved back to `StudentAttempt` so they feed the next history aggregation

6. **`PersonalizedModuleViewer.svelte`**
   - Renders generated learning module as structured sections (collapsible concept recap, worked examples, practice problems)
   - Practice problems are interactive (same MCQ renderer)
   - "Mark as done" → updates enrollment progress

**Relevant files**
- Create: `backend/app/services/learning_history_service.py`
- Create: `backend/app/api/v1/endpoints/tutor.py` — `/generate-test`, `/generate-module`, `/learning-profile`
- Create: `backend/app/services/personalized_generation_service.py`
- Create: `backend/app/schemas/personalized_item.py` — `LearningProfile`, `PersonalizedTestRequest`, `PersonalizedModuleRequest`
- Modify: `backend/app/api/v1/endpoints/questions.py` — `_build_inquiry_system_prompt` for `personalization_intent` mode
- Create: `trainer-web/src/lib/components/PersonalizedTestViewer.svelte`
- Create: `trainer-web/src/lib/components/PersonalizedModuleViewer.svelte`
- Create: `trainer-web/src/lib/api/tutor.ts` — `generateTest()`, `generateModule()`, `getLearningProfile()`

---

## Phase 5: Course Catalog & Teacher Dashboard

**Goal**: Browse/search courses, teacher course management UI.

### Steps

1. **Public course catalog** (`trainer-web/src/routes/courses/+page.svelte`)
   - Grid of course cards (cover image, title, teacher, price, rating)
   - Filters: subject, price range, rating, duration
   - Search bar with debounce
   - Featured courses banner

2. **Course detail page** (`trainer-web/src/routes/courses/[slug]/+page.svelte`)
   - Hero with cover image, title, teacher avatar
   - Pricing + Enroll CTA
   - Curriculum outline (module list, preview badges)
   - Learning outcomes, reviews (future), instructor bio

3. **Teacher course dashboard** (`trainer-web/src/routes/teacher/courses/+page.svelte`)
   - List of teacher's courses (draft/published)
   - Create new course button
   - Revenue stats (if paid courses)

4. **Course editor** (`trainer-web/src/routes/teacher/courses/[id]/edit/+page.svelte`)
   - Multi-step form: basics → modules → pricing → preview → publish
   - Module editor: drag-and-drop reorder, WYSIWYG for content, question selector for quizzes
   - Cover image upload (integrate existing document upload service)

**Relevant files**
- Create: `trainer-web/src/routes/courses/+page.svelte`
- Create: `trainer-web/src/routes/courses/[slug]/+page.svelte`
- Create: `trainer-web/src/routes/teacher/courses/+page.svelte`
- Create: `trainer-web/src/routes/teacher/courses/[id]/edit/+page.svelte`
- Create: `trainer-web/src/lib/components/CourseCard.svelte`
- Create: `trainer-web/src/lib/components/ModuleEditor.svelte`

---

## Phase 6: Payment Integration

**Goal**: Razorpay integration for paid courses. Ship a mock-payment flow now; wire real Razorpay later with a single swap.

### Step 1 — Mock checkout (ship now)

- **Enroll button state machine** (frontend only, no backend change needed yet):
  1. Student clicks "Buy" → button enters `processing` state
  2. Show a fullscreen/overlay **payment processing animation** (spinner + pulsing card icon + "Securing your enrollment…" copy) for ~1.8 s
  3. Call existing `POST /courses/{course_id}/enroll` directly (treat as free enroll internally)
  4. On success → transition animation to ✅ confetti burst + "You're enrolled!" for 1.2 s → redirect to `/student/learn/{slug}`
  5. On failure → show inline error toast, reset button

- **Backend**: `POST /courses/{course_id}/enroll` already creates an `Enrollment` record. For mock flow, pass `{ payment_provider: "mock", mock: true }` and backend creates a `Payment` record with `status = "completed"` and `provider = "mock"` — no real charge.

- **No env vars, no keys, no webhooks required for this step.**

### Step 2 — Real Razorpay (wire later, minimal diff)

1. **Razorpay setup**
   - Add `razorpay` to `requirements.txt`
   - Environment variables: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`
   - Frontend env: `PUBLIC_RAZORPAY_KEY_ID`

2. **Checkout endpoint** (`backend/app/api/v1/endpoints/payments.py`)
   - `POST /courses/{course_id}/checkout` — create Razorpay Order (`razorpay.orders.create`)
   - Returns `{ order_id, amount, currency, key_id }` to frontend

3. **Frontend Razorpay SDK flow** (replaces mock animation step 2–3 above)
   - Load Razorpay Checkout JS (`<script src="https://checkout.razorpay.com/v1/checkout.js">`)
   - Open `Razorpay({ key, order_id, amount, … })` modal
   - On `payment.success` → call `POST /payments/verify` with `{ razorpay_order_id, razorpay_payment_id, razorpay_signature }`
   - Backend verifies HMAC signature → creates Enrollment + Payment records
   - On `payment.failed` → show error toast

4. **Webhook handler** (belt-and-suspenders)
   - `POST /payments/webhook/razorpay` — verify `X-Razorpay-Signature`, handle `payment.captured`
   - Idempotent: skip if Enrollment already exists for this order

5. **Teacher payouts** (future phase)
   - Razorpay Route for automatic splits (platform fee vs. teacher earnings)

**Relevant files**
- Create: `backend/app/api/v1/endpoints/payments.py`
- Create: `backend/app/services/payment_service.py` (mock + razorpay implementations behind `PaymentProvider` interface)
- Modify: `backend/requirements.txt` — add `razorpay`
- Modify: `trainer-web/src/routes/courses/[slug]/+page.svelte` — enroll button state machine + animation
- Create: `trainer-web/src/lib/components/PaymentAnimation.svelte` — processing & success animations

---

## Verification

1. **Unit tests** — Course/Enrollment/Payment CRUD, vquest query service
2. **Integration tests** — Full enrollment flow (free + paid), module completion, progress tracking
3. **E2E tests** — Teacher creates course → publishes → student enrolls → completes module → AI tutor generates test
4. **Manual testing**:
   - Create course with 3 modules (content, quiz, video)
   - Enroll as student (free course first)
   - Complete modules, verify progress saves
   - Ask tutor "create a test for me" → verify generation

---

## Decisions

- **Separate Course vs. Subject**: Courses are teacher-authored packages; Subjects remain system-level taxonomy linked to questions. Courses reference subjects but add custom modules/pricing.
- **Question reuse**: Modules pull approved questions from existing vquest DB. Teachers don't re-upload — they search and attach.
- **Payment provider**: Razorpay (better India support, in-page modal UX). Mock flow ships first — clicking Buy runs an animation and enrolls immediately. Real Razorpay wires in as a single swap in `PaymentService` with no frontend state-machine changes.
- **Personalized generation**: Uses LLM with RAG from course content + templates. Not generating new curriculum — generating practice items per student.

---

## Further Considerations

1. **Rating/Review system** — Should courses have reviews? Recommend yes, but defer to Phase 7.
2. **Refund policy** — Who handles refunds? Recommend 7-day no-questions-asked via Stripe.
3. **Course versioning** — What happens if teacher updates a course after students enrolled? Recommend "versions" with enrollment pinned to version at enrollment time, but this adds complexity — could defer.
