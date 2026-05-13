# Multimodal Demo Image Notes

This public repository does not bundle proprietary manual screenshots or local fault photos.

If you want to run multimodal demos, prepare your own compliant images under `datasets/img/` and keep stable, descriptive filenames such as:

- `spark_plug_carbon_fouling_photo.png`
- `spark_plug_gap_out_of_spec_check.png`
- `starter_motor_connection_removal_check.png`
- `timing_chain_tensioner_lock_release_check.png`
- `valve_clearance_out_of_spec_shim_check.png`
- `crankshaft_balance_shaft_timing_mark_check.png`

## Recommended naming

Use:

- `part_name + fault_or_check_point + usage`

Examples:

- `spark_plug_carbon_fouling_photo`
- `spark_plug_gap_out_of_spec_check`
- `timing_chain_tensioner_lock_release_check`

## CRCO prompt templates

### 1) Spark plug carbon fouling

```text
Context:
The input is a field photo of a motorcycle engine spark plug. The goal is to combine visible evidence and the maintenance knowledge base to judge whether carbon fouling, ignition abnormality, or hard starting may be involved.

Role:
You are a motorcycle engine maintenance assistant skilled at combining component appearance with maintenance-manual retrieval.

Command:
Identify the main component and visible abnormal signs in the image, then retrieve manual content related to spark plug inspection, spark plug gap, carbon fouling handling, and hard starting.

Output:
1. Identified component
2. Visible abnormal signs
3. Most relevant manual knowledge
4. Recommended first inspection items
5. Any cited section or page reference
```

### 2) Starter motor removal

```text
Context:
The input is an engine-side assembly image. The goal is to identify the starter motor area and retrieve the related removal procedure.

Role:
You are a maintenance-procedure retrieval assistant.

Command:
Identify the starter-motor-related parts in the image and retrieve the manual steps for disconnecting wiring and removing fixing hardware.

Output:
1. Key identified parts
2. Suggested removal order
3. Precautions
4. Manual references
```

### 3) Timing chain tensioner

```text
Context:
The input is a timing-chain tensioner operation image. The goal is to understand preload, self-lock, and release actions and connect them to the manual.

Role:
You are an engine timing-system maintenance assistant.

Command:
Identify the component and action direction in the image, then retrieve manual content about tensioner preload, self-lock, release, and post-installation checks.

Output:
1. Component name
2. Meaning of the illustrated action
3. Relevant operating steps
4. Post-maintenance check points
5. Manual references
```

## Public-repo boundary

- Do not commit proprietary manuals.
- Do not commit copyrighted manual screenshots unless you have redistribution rights.
- Do not commit photos containing personal information, internal labels, or local-environment details.
