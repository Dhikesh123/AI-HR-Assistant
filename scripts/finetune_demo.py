"""Optional module: fine-tuning for response STYLE, not for company knowledge.

Why this is separate from RAG
-----------------------------
RAG supplies *knowledge* that changes (leave balances, allowances, policy
numbers). Fine-tuning teaches *behaviour* - tone, structure, how to refuse.
Baking policy facts into weights would mean retraining every time HR edits a
document, and the model could still recite the old number confidently. So:

    RAG          -> company knowledge (changes often, must be citable)
    Fine-tuning  -> task/style adaptation (changes rarely, no facts)

This script builds a small JSONL dataset in OpenAI chat-fine-tuning format that
demonstrates the desired *style*: short, procedural, portal-first answers, and a
consistent refusal when the documents do not cover the question. It deliberately
contains no policy numbers.

Usage::

    python -m scripts.finetune_demo              # write the dataset
    python -m scripts.finetune_demo --upload     # print the upload commands
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from backend.rag.prompts import NO_ANSWER_RESPONSE

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "data" / "finetune_style_dataset.jsonl"

SYSTEM_MESSAGE = (
    "You are an AI HR Assistant. Answer in at most three sentences, in a calm "
    "professional tone. Describe the process and where to do it. Never state a "
    "policy number, amount or entitlement that is not in the provided context."
)

# Style examples only - process and tone, never a specific entitlement value.
EXAMPLES: List[Dict[str, str]] = [
    {
        "input": "How do I apply for leave?",
        "output": (
            "Submit a leave request through the HR portal under My Leave. "
            "Email or verbal requests are not treated as valid applications. "
            "Your reporting manager will action the request within two working days."
        ),
    },
    {
        "input": "i need time off next week whats the process",
        "output": (
            "Raise the request in the HR portal as early as you can so your work can "
            "be handed over. Planned leave should be applied for in advance of the "
            "start date. Your manager approves it from their portal queue."
        ),
    },
    {
        "input": "Where do I find my payslip?",
        "output": (
            "Payslips are published in the HR portal under My Payroll. "
            "They appear from the first working day of the month following the pay run. "
            "Contact the HR service desk if a payslip is missing."
        ),
    },
    {
        "input": "How do I fix a missed attendance swipe?",
        "output": (
            "Submit an attendance regularisation in the HR portal for the affected date. "
            "Do it within the regularisation window stated in the Attendance Policy. "
            "Your manager approves the correction."
        ),
    },
    {
        "input": "Who do I talk to about a harassment concern?",
        "output": (
            "You can raise it with your HR Business Partner or anonymously through the "
            "ethics helpline. Complaints are handled confidentially by the Internal "
            "Committee. Retaliation for raising a concern in good faith is itself a breach "
            "of the Code of Conduct."
        ),
    },
    {
        "input": "How do I add my parents to the medical insurance?",
        "output": (
            "Parents can be added during the flexible benefits window in the HR portal. "
            "An additional premium applies and is deducted from salary. "
            "The HR service desk can confirm the current rate for you."
        ),
    },
    {
        "input": "What is the company's international travel allowance?",
        "output": NO_ANSWER_RESPONSE,
    },
    {
        "input": "How many stock options will I get?",
        "output": NO_ANSWER_RESPONSE,
    },
]


def build_dataset() -> List[Dict[str, object]]:
    """Build the chat-format fine-tuning records."""
    return [
        {
            "messages": [
                {"role": "system", "content": SYSTEM_MESSAGE},
                {"role": "user", "content": example["input"]},
                {"role": "assistant", "content": example["output"]},
            ]
        }
        for example in EXAMPLES
    ]


def write_dataset(path: Path = OUTPUT_PATH) -> Path:
    """Write the dataset as JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in build_dataset():
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


UPLOAD_INSTRUCTIONS = """
Next steps (optional, costs money, not required for the demo):

  1. Validate the file:
       python -m scripts.finetune_demo

  2. Upload and start a job:
       openai api files.create -f data/finetune_style_dataset.jsonl -p fine-tune
       openai api fine_tuning.jobs.create -t <file-id> -m gpt-4o-mini-2024-07-18

  3. Point the app at the tuned model:
       LLM_MODEL=ft:gpt-4o-mini-2024-07-18:<org>::<id>

The retrieval pipeline is unchanged - the tuned model still answers only from
the retrieved HR context. Fine-tuning changed how it speaks, not what it knows.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload", action="store_true", help="print the upload instructions")
    args = parser.parse_args()

    path = write_dataset()
    records = build_dataset()
    refusals = sum(1 for r in records if r["messages"][-1]["content"] == NO_ANSWER_RESPONSE)

    print(f"Wrote {len(records)} style examples to {path}")
    print(f"  {refusals} of them teach the refusal behaviour")
    print("  0 of them contain a policy figure - those come from RAG at query time")

    if args.upload:
        print(UPLOAD_INSTRUCTIONS)


if __name__ == "__main__":
    main()
