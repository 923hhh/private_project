# Retrieval Evaluation Templates

These files are public-safe evaluation templates for the knowledge retrieval module.

Included files:

- `motorcycle_engine_retrieval_eval.csv`: text-only retrieval evaluation set
- `motorcycle_engine_multimodal_eval.csv`: multimodal evaluation template

## Important public-repo constraints

This repository does not bundle:

- proprietary maintenance manuals
- copyrighted manual screenshots
- local evaluation outputs
- local image attachments

Before running the evaluation scripts, prepare your own compliant files in a private environment.

## How to use

Text-only evaluation:

```bash
cd backend
python scripts/run_motorcycle_retrieval_eval.py --dataset-csv ../datasets/validation/motorcycle_engine_retrieval_eval.csv
```

Multimodal evaluation:

1. Put your own compliant images under `datasets/img/`
2. Fill the `image_path` column in `motorcycle_engine_multimodal_eval.csv`
3. Provide a compliant manual PDF at `datasets/pdf/摩托车发动机维修手册.pdf`, or pass a custom `--pdf-path`

```bash
cd backend
python scripts/run_motorcycle_retrieval_eval.py --dataset-csv ../datasets/validation/motorcycle_engine_multimodal_eval.csv --pdf-path ../datasets/pdf/your_manual.pdf
```

## Notes

- The script supports both text-only rows and rows with `image_path + query`.
- If an `image_path` is provided, the script will encode the image as `image_base64` and call `/api/v1/knowledge/search`.
- Evaluation outputs are written to `backend/evaluation/results/` and should remain ignored in git.
