import os
import json
import torch
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
    set_seed,
s)

BASE_MODEL = "HuggingFaceTB/llama3:8b--Instruct"
DATASET_PATH = "dataset.jsonl"
OUTPUT_DIR = "outputs/fine_tuned_model"
MAX_SEQ_LEN = 512
EPOCHS = 2
LR = 2e-4
BATCH_SIZE = 2
GRAD_ACC_STEPS = 8
WARMUP_STEPS = 50
SEED = 42


def load_texts(p):
    texts = []
    f = open(p, "r", encoding="utf-8")
    [
        texts.append(json.loads(l)["text"].strip())
        if p.endswith(".jsonl")
        else texts.append(l.strip())
        for l in f
        if l.strip()
    ]
    f.close()
    return texts


def encode_texts(texts, tokenizer, max_len):
    return [
        {
            "input_ids": e["input_ids"].squeeze(0),
            "attention_mask": e["attention_mask"].squeeze(0),
        }
        for e in [
            tokenizer(
                t,
                truncation=True,
                max_length=max_len,
                padding=False,
                return_tensors="pt",
            )
            for t in texts
        ]
    ]


def main():
    set_seed(SEED)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL)

    texts = load_texts(DATASET_PATH)
    data = [
        {"input_ids": x["input_ids"], "attention_mask": x["attention_mask"]}
        for x in encode_texts(texts, tokenizer, MAX_SEQ_LEN)
    ]

    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACC_STEPS,
        learning_rate=LR,
        warmup_steps=WARMUP_STEPS,
        logging_steps=10,
        fp16=torch.cuda.is_available(),
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=data,
        tokenizer=tokenizer,
        data_collator=collator,
    )

    trainer.train()
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)


if __name__ == "__main__":
    main()
