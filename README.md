<div align=center><h1>
    AppCIF-Bench: An Application-Level Complex Instruction<br>
    Following Benchmark for Large Language Models
</h1></div>

<p align="center">
  🌐 <a href="https://ac2333.github.io/AppCIF/" target="_blank">Website</a> • 📂 <a href="data/" target="_blank">Dataset</a>
</p>

## 🔔 News

- [2026] AppCIF-Bench has been accepted to **NeurIPS 2026**! 🎉
- [2026] The **evaluation code, Code Simulation Engines, and dataset** (Chinese and English) are released. 🚀

## 📖 Introduction

Complex Instruction Following (CIF) underpins the deployment of large language models (LLMs) in production-grade applications. It demands stable, precise outputs across long horizons, deeply nested rules, and multi-turn interactions, yet predominantly atomic, short-horizon benchmarks miss this real-world logical depth and distractor pressure.

**AppCIF** is the first application-level CIF benchmark. It stratifies difficulty along two axes: **Horizon Length (*H*)**, the span over which distractors accumulate and critical signals must be tracked, and **Logical Depth (*L*)**, the depth of nested rules. Its **Prompt-as-Environment** paradigm pairs complex system prompts (~14k words at L4) with executable Code Simulation Engines (~3.5k lines of Python on average) to sustain rigorous state-machine deduction.

Across 12 evaluated LLMs, Hard Satisfaction Rate ranges from only **1.1% to 45.9%**, exposing bottlenecks in long-horizon, distractor-laden instruction execution.

<p align="center">
  <img src="figure/framework.webp" alt="AppCIF-Bench data construction pipeline" width="100%"/>
</p>

## 🧩 Benchmark Details

AppCIF contains **466 samples** and **3,017 atomic rubrics** across five application scenarios and four complexity levels, in Chinese and English. The counts below refer to the released version (v1.1); the paper reports the initial version with 2,998 rubrics (see [Version notes](#-version-notes)).

| Scenario | L1 | L2 | L3 | L4 | Total |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Curriculum Planning | 38 | 38 | 0 | 0 | 76 |
| Travel Planning | 25 | 17 | 8 | 0 | 50 |
| Numeric-Intensive | 23 | 0 | 23 | 0 | 46 |
| Role-Playing | 27 | 16 | 11 | 0 | 54 |
| Real-world Simulation | 21 | 49 | 80 | 90 | 240 |
| **Total samples** | **134** | **120** | **122** | **90** | **466** |
| **Total rubrics** | **730** | **688** | **803** | **796** | **3,017** |

The 240 Real-world Simulation samples cover six sub-scenarios of 40 samples each: Concert Budgeting, Tomb Exploration, TCM Diagnosis, Case Adjudication, Power Grid Dispatch, and Time-Space Trading.

| Level | Name | Pressure |
| :--- | :--- | :--- |
| L1 | Precise Execution | Short *H*, few-step *L* |
| L2 | Multi-turn Goal Retention | Long *H* with local distractors, multi-step *L* |
| L3 | Information Reorganization Under High Noise | Long *H* with global distractors, multi-step *L* |
| L4 | Extreme Pressure Deduction | Extreme *H*, deep multi-step *L* |

Models are scored with two metrics under an LLM-as-a-judge protocol:

- **SSR (Soft Satisfaction Rate)**: the share of all rubrics that are satisfied.
- **HSR (Hard Satisfaction Rate)**: the share of samples with every rubric satisfied.

## 🛠️ Quick Start

### 1. Install

Python 3.10 or later is required.

```bash
git clone https://github.com/Tencent-Hunyuan/AppCIF-Bench.git
cd AppCIF-Bench
pip install -r requirements.txt
```

### 2. Dataset

The dataset is in [`data/`](data/): `AppCIF_bench_dataset.jsonl` (Chinese) and `AppCIF_bench_dataset_en.jsonl` (English), 466 samples each, with the same IDs and the same rubrics per sample. Each sample contains the system prompt, the earlier dialogue turns (history), the final question, its rubrics, and its scenario, category and difficulty level; the Chinese file also includes the ground-truth derivation behind the rubrics.

For Chinese–English comparisons, `cross_lingual_strata.json` lists 18 Role Playing samples to report separately, because they require Chinese-specific output or carry a constraint tied to the language of the prompt; the other 448 samples are directly comparable.

### 3. Run an evaluation

Set the API key of each model you evaluate, and `ARK_API_KEY` for the default judge (Doubao-Seed-2.0-lite), in the environment or in a `.env` file. Endpoints, request parameters and key names are listed in [`eval/model_registry.py`](eval/model_registry.py); to use other models, including local ones, see [Use your own models](#4-use-your-own-models).

The commands below evaluate the Chinese file; run them on the English file the same way. Re-running a command resumes where it stopped and retries failed samples. A missing API key, or a key, permission or model name rejected by the provider, stops the command at once.

**Step 1: Collect model answers.**

```bash
python run_eval.py pull_answer \
  --data_file data/AppCIF_bench_dataset.jsonl \
  --model_name Doubao-Seed-2.0-Pro-high \
  --output_dir results \
  --concurrency 20
```

**Step 2: Judge the answers.** The judge checks each rubric separately, given only the rubric, the final question and the answer (prompt in [`eval/eval_pipeline.py`](eval/eval_pipeline.py)). Use `--eval_model` to change the judge.

```bash
python run_eval.py evaluate \
  --data_file data/AppCIF_bench_dataset.jsonl \
  --model_name Doubao-Seed-2.0-Pro-high \
  --answers_file results/answers_Doubao-Seed-2.0-Pro-high.jsonl \
  --output_dir results \
  --concurrency 20
```

**Step 3: Compute SSR and HSR.** Samples without an answer or a judgment count as failures. If you changed the judge, pass the same `--eval_model` here.

```bash
python run_eval.py calculate_accuracy \
  --data_file data/AppCIF_bench_dataset.jsonl \
  --model_names Doubao-Seed-2.0-Pro-high \
  --eval_dir results \
  --output_dir results
```

Scores by level and by category are written to `results/accuracy_summary.xlsx` (the `constraint_*` columns are SSR and the `sample_*` columns are HSR), and per-rubric verdicts to `results/results_tagged.jsonl`.

### 4. Use your own models

To answer or judge with a model that is not in the registry, such as a local model, register it in a Python file and pass the file with `--models_file` to `pull_answer` and `evaluate`. A model is either an OpenAI-compatible endpoint (vLLM, SGLang, Ollama, a gateway, ...) or a Python function that takes the messages in OpenAI format and returns the reply text:

```python
# my_models.py
from eval.model_registry import register_model

# OpenAI-compatible endpoints: model_id defaults to the name; without api_key_env no key is needed
register_model("Qwen3-32B-local", base_url="http://localhost:8000/v1", model_id="Qwen/Qwen3-32B")
register_model("my-judge", base_url="http://localhost:8001/v1", api_key_env="MY_JUDGE_API_KEY",
               extra_params={"max_tokens": 8192})

# A Python function, e.g. wrapping a Hugging Face model
@register_model("my-hf-model")
def generate(messages: list[dict]) -> str:
    ...
```

```bash
python run_eval.py pull_answer --models_file my_models.py \
  --data_file data/AppCIF_bench_dataset.jsonl \
  --model_name my-hf-model \
  --output_dir results \
  --concurrency 1

python run_eval.py evaluate --models_file my_models.py \
  --data_file data/AppCIF_bench_dataset.jsonl \
  --model_name my-hf-model \
  --answers_file results/answers_my-hf-model.jsonl \
  --eval_model my-judge \
  --output_dir results

python run_eval.py calculate_accuracy \
  --data_file data/AppCIF_bench_dataset.jsonl \
  --model_names my-hf-model \
  --eval_model my-judge \
  --eval_dir results \
  --output_dir results
```

An answer request contains the system prompt, the earlier turns and the final question; a judge request is a single user message with the judge prompt. `extra_params` are sent in the request body unchanged (e.g. `max_tokens` or a thinking switch); other decoding parameters stay at the server default. A function is called from up to `--concurrency` threads at once, so use `--concurrency 1` for a model that cannot serve parallel calls.

Without a models file, an unregistered model name is sent to the OpenAI-compatible endpoint set by `OPENAI_BASE_URL` (default `https://api.openai.com/v1`) and `OPENAI_API_KEY`. Scores depend on the judge (see [Version notes](#-version-notes)), so report which judge you used.

## ⚙️ Code Simulation Engines

[`code_simulation_engines/`](code_simulation_engines/) contains the six executable engines that produce ground truth for the Real-world Simulation tasks. They require only the Python standard library.

| L4 archetype | Engine | Data category |
| :--- | :--- | :--- |
| Optimization & Planning | Concert audit | Concert Budgeting |
| Optimization & Planning | Spatiotemporal trade | Time-Space Trading |
| Decision-Tree State Machine | Rule-based adjudication | Case Adjudication |
| Decision-Tree State Machine | Traditional-medicine diagnosis | TCM Diagnosis |
| Spatial / Multi-Rule | Power-grid operation | Power Grid Dispatch |
| Spatial / Multi-Rule | Tomb exploration | Tomb Exploration |

Run one bundled example through every engine from the repository root:

```bash
python -m code_simulation_engines.run_smoke_tests
```

[`code_simulation_engines/structured_inputs.jsonl`](code_simulation_engines/structured_inputs.jsonl) holds the engine inputs of all 240 simulation samples. To print the engine output for one sample, or to re-derive the released rubrics and compare them with the data:

```bash
python -m code_simulation_engines.spatial_multi_rule.tomb_exploration.tomb_exploration_engine tomb_18
python -m code_simulation_engines.regenerate_gold
```

See the [engine README](code_simulation_engines/README.md) for entry points, input formats, and known differences.

## 🏆 Leaderboard

Performance of 12 LLMs on the Chinese version of AppCIF, as reported in the paper (initial version of the data, judged by Doubao-Seed-1.6-1015), sorted by **HSR Avg**. Best results in each column are in **bold**. Numbers under each column are rubric counts (SSR) or sample counts (HSR).

<table>
  <thead>
    <tr>
      <th rowspan="2" align="left">Model</th>
      <th colspan="5">SSR (%)</th>
      <th colspan="5">HSR (%)</th>
    </tr>
    <tr>
      <th>L1<br><sub>727</sub></th><th>L2<br><sub>678</sub></th><th>L3<br><sub>798</sub></th><th>L4<br><sub>795</sub></th><th>Avg<br><sub>2,998</sub></th>
      <th>L1<br><sub>134</sub></th><th>L2<br><sub>120</sub></th><th>L3<br><sub>122</sub></th><th>L4<br><sub>90</sub></th><th>Avg<br><sub>466</sub></th>
    </tr>
  </thead>
  <tbody>
    <tr><td><strong>GPT-5.4-xhigh</strong></td><td align="center">79.1</td><td align="center"><strong>81.0</strong></td><td align="center"><strong>77.4</strong></td><td align="center"><strong>75.9</strong></td><td align="center"><strong>78.2</strong></td><td align="center"><strong>50.8</strong></td><td align="center"><strong>54.2</strong></td><td align="center"><strong>43.4</strong></td><td align="center"><strong>31.1</strong></td><td align="center"><strong>45.9</strong></td></tr>
    <tr><td>Gemini-3.1-Pro-Preview</td><td align="center"><strong>82.4</strong></td><td align="center">76.6</td><td align="center">73.2</td><td align="center">53.1</td><td align="center">70.9</td><td align="center">49.3</td><td align="center">39.2</td><td align="center">32.8</td><td align="center">8.9</td><td align="center">34.6</td></tr>
    <tr><td>Doubao-Seed-2.0-Pro-high</td><td align="center">66.6</td><td align="center">62.8</td><td align="center">52.5</td><td align="center">34.7</td><td align="center">53.5</td><td align="center">30.6</td><td align="center">25.0</td><td align="center">16.4</td><td align="center">2.2</td><td align="center">20.0</td></tr>
    <tr><td>GLM-5.1</td><td align="center">65.2</td><td align="center">58.3</td><td align="center">48.6</td><td align="center">30.6</td><td align="center">50.0</td><td align="center">23.9</td><td align="center">10.8</td><td align="center">4.9</td><td align="center">0.0</td><td align="center">10.9</td></tr>
    <tr><td>Gemini-3-Flash-Preview</td><td align="center">66.4</td><td align="center">56.8</td><td align="center">41.7</td><td align="center">23.8</td><td align="center">46.4</td><td align="center">17.9</td><td align="center">14.2</td><td align="center">5.7</td><td align="center">0.0</td><td align="center">10.3</td></tr>
    <tr><td>Kimi-K2.5-Thinking</td><td align="center">60.4</td><td align="center">46.2</td><td align="center">40.4</td><td align="center">25.0</td><td align="center">42.5</td><td align="center">14.9</td><td align="center">10.0</td><td align="center">6.6</td><td align="center">0.0</td><td align="center">8.6</td></tr>
    <tr><td>Qwen-3.6-Plus-Thinking</td><td align="center">57.4</td><td align="center">50.7</td><td align="center">41.7</td><td align="center">30.7</td><td align="center">44.7</td><td align="center">14.9</td><td align="center">11.7</td><td align="center">2.5</td><td align="center">0.0</td><td align="center">7.9</td></tr>
    <tr><td>Grok-4.2</td><td align="center">55.3</td><td align="center">45.6</td><td align="center">32.7</td><td align="center">16.1</td><td align="center">36.7</td><td align="center">11.2</td><td align="center">5.8</td><td align="center">1.6</td><td align="center">0.0</td><td align="center">5.2</td></tr>
    <tr><td>DeepSeek-V3.2-Thinking</td><td align="center">48.0</td><td align="center">44.0</td><td align="center">36.5</td><td align="center">29.9</td><td align="center">39.2</td><td align="center">7.5</td><td align="center">3.3</td><td align="center">4.1</td><td align="center">0.0</td><td align="center">4.1</td></tr>
    <tr><td>Xiaomi-MiMo-V2-Pro</td><td align="center">42.0</td><td align="center">38.4</td><td align="center">31.8</td><td align="center">19.6</td><td align="center">32.5</td><td align="center">6.0</td><td align="center">4.2</td><td align="center">2.5</td><td align="center">0.0</td><td align="center">3.4</td></tr>
    <tr><td>Minimax-M2.7</td><td align="center">35.5</td><td align="center">29.7</td><td align="center">22.8</td><td align="center">12.6</td><td align="center">24.7</td><td align="center">3.7</td><td align="center">4.2</td><td align="center">0.0</td><td align="center">1.1</td><td align="center">2.4</td></tr>
    <tr><td>Xiaomi-MiMo-V2-Omni</td><td align="center">39.1</td><td align="center">32.3</td><td align="center">27.1</td><td align="center">16.1</td><td align="center">28.3</td><td align="center">1.5</td><td align="center">0.8</td><td align="center">1.6</td><td align="center">0.0</td><td align="center">1.1</td></tr>
  </tbody>
</table>

> Scores are judged by Doubao-Seed-1.6-1015. **Avg** is the sample- or rubric-weighted global average.

## 📝 Version notes

This repository releases **v1.1** of AppCIF-Bench. The 466 samples, scenarios, difficulty levels and task definitions are the same as in the paper. Compared with the initial version used for the paper results:

- **English version**: a parallel English translation with the same sample IDs and the same number of rubrics per sample.
- **Corrections**: errors found in a post-submission audit (gold values, rubric wording, derivations, rulebook rules, and a few dialogue turns) were corrected, and the Code Simulation Engines were fixed accordingly. Of the 2,998 original rubrics, 1,084 were revised, 1 was removed and 20 were added (3,017 in total); 149 samples are unchanged.
- **Judging notes**: some rubrics end with a short note in parentheses that lists accepted equivalent surface forms (e.g. decimal places, thousands separators) or states a format requirement that the system prompt already makes (e.g. a verdict label must keep its brackets).
- **Judge**: Doubao-Seed-1.6, the judge of the paper results, is no longer served; results on v1.1 are judged by Doubao-Seed-2.0-lite (`doubao-seed-2-0-lite-260428`) with the same judge prompt.

Scores on v1.1 are therefore not directly comparable with the paper results; re-evaluation results on v1.1 are reported in Appendix J of the paper. Scores also depend on the judge, so report which judge you used and compare models under the same judge.


## 📜 License

- **Code**: the evaluation code and the Code Simulation Engines are released under the [Apache License 2.0](LICENSE).
- **Dataset**: the files in [`data/`](data/) and the engine inputs in [`code_simulation_engines/structured_inputs.jsonl`](code_simulation_engines/structured_inputs.jsonl) are released under [CC BY-NC 4.0](data/LICENSE) ([summary](https://creativecommons.org/licenses/by-nc/4.0/)) and may only be used for non-commercial purposes.

## 📪 Support

For questions and support, please open an issue on GitHub.
