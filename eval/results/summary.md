## sales

| System | n | Answer correct | Completed | Detect P | Detect R | Errors handled | Damage | Tool-call OK | Recovery | Approvals (med) | Latency s (med) | Tokens (med) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 stakeholder baseline | 20 | 0% | 95% | 0.80 | 0.61 | 19% | 0 | n/a | n/a | n/a | 0.0 | 0 |
| B1 fixed script | 20 | 70% | 100% | 0.74 | 0.80 | 80% | 0 | n/a | n/a | n/a | 0.0 | 0 |
| B2 single LLM call | 20 | 30% | 80% | 0.70 | 0.75 | 68% | 195 | n/a | n/a | n/a | 23.4 | 2,327 |
| DataSage (235B) | 20 | 85% | 100% | 0.84 | 0.85 | 89% | 0 | 100% | n/a | 3.0 | 152.3 | 56,024 |
| DataSage (30B) | 20 | 65% | 100% | 0.78 | 0.76 | 75% | 0 | 100% | 100% | 3.0 | 15.5 | 55,358 |
| DataSage, all risky fixes rejected | 10 | 30% | 100% | 0.88 | 0.86 | 47% | 0 | 100% | n/a | 2.5 | 171.4 | 50,410 |
| DataSage, no validator | 10 | 100% | 100% | 0.88 | 0.88 | 95% | 0 | 100% | n/a | 2.5 | 220.7 | 53,786 |
| DataSage (235B) + exclusion rule | 20 | 100% | 100% | 0.87 | 0.87 | 97% | 0 | 100% | n/a | 3.0 | 192.9 | 57,032 |
| DataSage (30B) + exclusion rule | 20 | 95% | 100% | 0.81 | 0.76 | 89% | 0 | 100% | n/a | 2.0 | 15.2 | 56,089 |
| DataSage (30B) + rule, strict approver | 20 | 100% | 100% | 0.83 | 0.79 | 92% | 0 | 100% | n/a | 2.0 | 14.3 | 54,481 |

## penguins

| System | n | Answer correct | Completed | Detect P | Detect R | Errors handled | Damage | Tool-call OK | Recovery | Approvals (med) | Latency s (med) | Tokens (med) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 stakeholder baseline | 20 | 5% | 80% | 1.00 | 0.60 | 24% | 0 | n/a | n/a | n/a | 0.0 | 0 |
| B1 fixed script | 20 | 45% | 100% | 1.00 | 0.81 | 80% | 0 | n/a | n/a | n/a | 0.0 | 0 |
| B2 single LLM call | 20 | 45% | 100% | 0.86 | 0.74 | 79% | 25 | n/a | n/a | n/a | 27.9 | 2,478 |
| DataSage (235B) | 20 | 85% | 100% | 0.88 | 0.78 | 84% | 0 | 100% | n/a | 2.0 | 196.9 | 51,990 |
| DataSage (30B) | 20 | 70% | 100% | 0.88 | 0.79 | 85% | 0 | 100% | n/a | 2.0 | 14.9 | 57,050 |
| DataSage, all risky fixes rejected | 10 | 0% | 100% | 0.90 | 0.76 | 55% | 0 | 100% | n/a | 2.0 | 158.3 | 51,284 |
| DataSage, no validator | 10 | 80% | 100% | 0.90 | 0.76 | 83% | 0 | 100% | n/a | 2.0 | 194.3 | 51,371 |
| DataSage (235B) + exclusion rule | 20 | 100% | 100% | 0.88 | 0.77 | 96% | 0 | 100% | n/a | 2.0 | 215.0 | 52,428 |
| DataSage (30B) + exclusion rule | 20 | 85% | 100% | 0.88 | 0.77 | 92% | 0 | 100% | n/a | 2.0 | 15.1 | 55,282 |
| DataSage (30B) + rule, strict approver | 20 | 85% | 100% | 0.88 | 0.77 | 91% | 0 | 100% | n/a | 2.0 | 13.2 | 57,418 |

## sales-heldout

| System | n | Answer correct | Completed | Detect P | Detect R | Errors handled | Damage | Tool-call OK | Recovery | Approvals (med) | Latency s (med) | Tokens (med) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 stakeholder baseline | 20 | 0% | 95% | 0.89 | 0.70 | 23% | 0 | n/a | n/a | n/a | 0.0 | 0 |
| B1 fixed script | 20 | 40% | 100% | 0.79 | 0.86 | 78% | 0 | n/a | n/a | n/a | 0.0 | 0 |
| B2 single LLM call | 20 | 85% | 100% | 0.79 | 0.77 | 86% | 2 | n/a | n/a | n/a | 27.3 | 2,214 |
| DataSage (235B) | 20 | 80% | 90% | 0.91 | 0.77 | 81% | 0 | 100% | 100% | 2.0 | 210.5 | 51,404 |
| DataSage (30B) | 20 | 95% | 100% | 0.86 | 0.76 | 84% | 0 | 100% | n/a | 3.0 | 14.8 | 61,856 |
| DataSage (235B) + exclusion rule | 20 | 80% | 95% | 0.89 | 0.77 | 86% | 0 | 99% | 100% | 2.5 | 156.3 | 54,037 |
| DataSage (30B) + exclusion rule | 20 | 90% | 100% | 0.88 | 0.89 | 88% | 0 | 100% | n/a | 2.0 | 15.1 | 65,225 |
| DataSage (30B) + rule, strict approver | 20 | 90% | 100% | 0.88 | 0.89 | 88% | 0 | 100% | n/a | 2.0 | 17.3 | 68,653 |

## penguins-heldout

| System | n | Answer correct | Completed | Detect P | Detect R | Errors handled | Damage | Tool-call OK | Recovery | Approvals (med) | Latency s (med) | Tokens (med) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 stakeholder baseline | 20 | 5% | 70% | 1.00 | 0.55 | 23% | 0 | n/a | n/a | n/a | 0.0 | 0 |
| B1 fixed script | 20 | 30% | 100% | 1.00 | 0.75 | 76% | 0 | n/a | n/a | n/a | 0.0 | 0 |
| B2 single LLM call | 20 | 35% | 100% | 0.87 | 0.81 | 66% | 29 | n/a | n/a | n/a | 30.2 | 2,534 |
| DataSage (235B) | 20 | 45% | 100% | 0.82 | 0.74 | 74% | 0 | 100% | 100% | 2.0 | 222.1 | 52,740 |
| DataSage (30B) | 20 | 40% | 100% | 0.82 | 0.72 | 62% | 0 | 100% | n/a | 2.0 | 14.1 | 55,528 |
| DataSage (235B) + exclusion rule | 20 | 95% | 100% | 0.82 | 0.70 | 97% | 0 | 100% | n/a | 2.0 | 150.8 | 52,608 |
| DataSage (30B) + exclusion rule | 20 | 80% | 100% | 0.79 | 0.61 | 85% | 0 | 100% | 100% | 2.0 | 13.2 | 55,258 |
| DataSage (30B) + rule, strict approver | 20 | 65% | 100% | 0.78 | 0.60 | 83% | 0 | 100% | n/a | 2.0 | 12.7 | 51,670 |
