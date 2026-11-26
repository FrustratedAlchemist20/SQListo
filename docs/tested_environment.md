# Tested environment

## Python environment

- Python: 3.11.15
- NumPy: 2.4.6
- Pandas: 3.0.3
- PyArrow: 24.0.0

## Local inference engine

- Engine: llama.cpp
- Build: 9700
- Commit: 9724f664e803e70eb8d046a3fac411122ad42ff7
- Compiler: GNU 14.3.1
- Platform: Linux x86_64

## Language model

- Model: Qwen2.5-Coder-1.5B-Instruct
- Format: GGUF
- Quantization: Q4_K_M
- Context size: 8192
- Parallel requests: 1
- Inference threads: 3
- Batch threads: 3

## Demonstration dataset

- Molecules: Azaconazole and Difenoconazole
- Electronic structure method label: uB3LYP
- Excitation label: ZPEx3
- Trajectories: 638
- Stored frames: 3560058
- Fragment analyses: 638
- Stored fragments: 1137

## Validation status

Preliminary functional testing.
Further regression and installation tests are required.
