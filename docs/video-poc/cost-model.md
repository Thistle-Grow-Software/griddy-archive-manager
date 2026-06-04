# v1 video delivery — projected Cloudflare cost (TGF-363, AC4)

Projected from local PoC measurements against published Cloudflare R2 + Workers pricing (no cloud resources were provisioned). Accuracy target: ~10x — enough to distinguish ~$10/mo from ~$1000/mo.

## Inputs

- Packaged catalog size: **2.95 TiB** (3,242 GB billed)
- Estimated games in catalog: **1,204**
- Objects fetched per clean stream: **326** (manifest + init + media segments)

## Pricing assumptions (USD)

- R2 storage: $0.015/GB-month, egress $0
- R2 Class A (writes): $4.5/million
- R2 Class B (reads): $0.36/million
- Workers: $5.0/mo + $0.3/million beyond 10M included

## Projected monthly cost by viewing volume

| Scenario | Storage | R2 reads | R2 writes | Workers | **Total/mo** |
| --- | --- | --- | --- | --- | --- |
| Pilot (100 streams/mo) | $48.63 | $0.01 | $0.15 | $5.00 | **$53.80** |
| Small (1k streams/mo) | $48.63 | $0.15 | $0.15 | $5.00 | **$53.93** |
| Active (10k streams/mo) | $48.63 | $1.47 | $0.15 | $5.00 | **$55.25** |
| Heavy (100k streams/mo) | $48.63 | $14.67 | $0.15 | $14.22 | **$77.68** |

## Takeaway

Storage dominates at low volume (~$49/mo for the whole catalog) and is fixed; request costs scale with viewing but stay small because R2 reads and Worker requests are cheap and egress is free. Even at 100k streams/month the total stays comfortably in the tens of dollars, confirming the ADR-0008 approach is firmly in the ~$10s/mo class, not ~$1000s/mo.
