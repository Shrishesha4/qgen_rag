# AI-Powered Education Platform: The "Self-Correcting" Dual-Engine Architecture

## 1. Project Vision
You are an Expert AI Systems Architect. Your mission is to build a **Self-Improvement Loop** for educational content generation.
The platform allows **Teachers** to generate questions and **Students (Vetters)** to review them.
**The "Secret Sauce":** The system uses a **Dual-Engine Strategy**:
1.  **Cloud Engine (DeepSeek V3 API)**: Generates high-quality content at scale.
2.  **Local Engine (DeepSeek-R1-Distill-Llama-70B/30B)**: Runs locally to *learn* from vetters, *critique* generations before humans see them, and eventually *fine-tune itself* to replace the cloud engine.

## 2. Core Architecture: The "Teacher-Vetter-Training" Loop

### Phase 1: High-Quality Generation (Cloud)
- **Actor:** Teacher
- **Action:** Requests questions (Topic: "Photosynthesis", Difficulty: "Hard").
- **Start State:**
  - System uses `pgvector` to find **3 Approved Questions** (Few-Shot Examples).
  - System uses `pgvector` to find **Top 3 Rejection Reasons** for this topic (Negative Constraints).
  - **Prompt Construction**: Dynamically assembled using "Learned Rules" from previous feedback.

### Phase 2: The "Constitutional AI" Filter (Local / Hybrid)
- **Before** the question reaches the Vetter, it passes through an **Automated Critique Agent** (Local DeepSeek).
- **The Constitution**: A set of rules (e.g., "Must be solvable," "No ambiguity," "Correct Answer Key").
- **Process**:
  1. Local Model reads the generated question.
  2. Local Model critiques it against the Constitution.
  3. If Score < 4/5 -> **Auto-Reject/Regenerate** (Teacher never sees bad output).
  4. If Score >= 4/5 -> **Forward to Vetter**.

### Phase 3: Human Vetting & Data Capture (The Gold Mine)
- **Actor:** Student (Vetter)
- **Interface:** "Tinder-style" or Queue-based review.
- **Actions**:
  - **Approve**: "This is perfect." -> Stored as **positive training sample**.
  - **Edit & Approve**: "Good, but spelling error." -> System stores **(Original, Edited)** pair for DPO (Direct Preference Optimization).
  - **Reject**: "Too vague." -> Stored as **negative training sample** with reasoning.

### Phase 4: The Training Pipeline (Local DeepSeek-30B)
This runs as a background service (`TrainingService`), independent of the web app.
1.  **SFT (Supervised Fine-Tuning) Data Prep**:
    - Daily job aggregates `Approved` questions into `{instruction, input, output}` JSONL format.
2.  **DPO (Direct Preference Optimization)**:
    - Uses triplets: `{Prompt, Chosen (Edited/Approved), Rejected (Original/Bad)}`.
    - This creates a **Reward Model** that aligns the local model with the Vetter's preferences.
3.  **Fine-Tuning Execution**:
    - Uses `LoRA` (Low-Rank Adaptation) to efficiently fine-tune the Local DeepSeek model on the captured data.

## 3. Web Application Specifications

### A. Tech Stack
- **Frontend**: SvelteKit + Tailwind CSS + Framer Motion.
- **Backend API**: Python FastAPI (Extended).
- **Database**: PostgreSQL + `pgvector`.
- **Local Inference**: `Ollama` or `vLLM` running DeepSeek-R1-30B.

### B. User Experience & Theming
**Themes**: 5 Global Themes (Ice, Water, Fire, Earth, Night) affecting background (images/gradients) and primary colors.
**Responsive**: Mobile-first design for Vetters (on the go).

### C. Roles
1.  **Teacher (Generator)**:
    - Dashboard: "Create Assessment".
    - Analytics: "Vetter Approval Rate" (How good is the AI?).
2.  **Vetter (judge)**:
    - Dashboard: "Vetting Queue".
    - Stats: "Accuracy Score" (Agreement with other vetters/Gold standards).

## 4. API & Database Requirements

### New Database Tables
1.  **`vetting_logs`**:
    - `question_id`, `vetter_id`, `decision` (approve/reject/edit), `edit_diff`, `rejection_reason_vector`.
2.  **`training_pairs`**:
    - `prompt`, `chosen_response`, `rejected_response` (For DPO).
3.  **`model_versions`**:
    - `version_id`, `base_model`, `lora_adapter_path`, `is_active`.

### New Endpoints
- `POST /api/vetting/submit`: Handles complex feedback (edits, reasons).
- `GET /api/training/status`: Monitoring the local fine-tuning job.
- `POST /api/training/trigger`: Manually trigger a fine-tuning run (Admin).

## 5. Implementation Roadmap (The "Kickstarter" Phase)

### Step 1: Frontend Foundations
- Scaffold SvelteKit app.
- Build the **Theme Context** (Ice/Fire/Water...).
- Build **Dual Login** Screens (Teacher/Vetter).

### Step 2: The Vetting UI
- Create the "Card Stack" or "Queue" component.
- Implement the "Edit" vs "Reject" flow with required metadata.

### Step 3: Backend Vetting Logic
- Enhance `vetter.py` endpoints to store **DPO Pairs**.
- If a vetter *edits* a question, save the *Original* as "Rejected" and *New* as "Chosen".

### Step 4: The Local "Critique" Agent (RAG)
- Implement a Python service that calls `Ollama` (Local DeepSeek).
- Before saving a generated question, pass it through `CritiqueService`.

## 6. Definition of Success
1. **Zero-Shot Generation**: DeepSeek API generates a question.
2. **Auto-Critique**: Local Model scores it.
3. **Human Vetting**: Vetter fixes a typo.
4. **Learning**: System saves the (Typo -> Fixed) pair.
5. **Next Run**: Local model, fine-tuned on that fix, *automatically corrects* similar typos in future generations.
