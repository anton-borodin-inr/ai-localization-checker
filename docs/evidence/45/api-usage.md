# Issue 45 API accounting

38 / 100 requests; peak estimate **USD 0.015411696**; off-peak estimate USD 0.0077058480; unknown reserve USD 0; limit USD 1.00. All 38 attempts returned validated responses; two are not_checked due to partial readability. No API error, transport retry or invalid response occurred. No further calls are needed.

Usage totals: `{"prompt_tokens": 69768, "completion_tokens": 3147, "total_tokens": 72915, "prompt_cache_hit_tokens": 31616, "prompt_cache_miss_tokens": 38152}`.

Every invocation used `uv run --env-file .env --no-sync l10n-check --image <PNG> --runs-dir data/runs --max-requests 1`. The task wrapper verifies screen/capture provenance and frozen hashes, reserves worst-case request cost before the call, locks/reconciles the ledger and records unknown/failure outcomes without treating them as clean. Only the project provider module contacts DeepSeek. The agent never reads, prints or copies .env or the key. The ignored .env path is a symlink to the existing project key file, not a copy.

The unchanged provider uses deepseek-flash, non-thinking, temperature 0, original PNG detail, JSON object mode, max_tokens 4096, 120 s timeout and no transport retries. The API reports only a model alias plus system_fingerprint, not an immutable revision. Tariff verification and conservative USD 0.319488 per-request reserve are in [budget-policy.json](budget-policy.json); the provider tariff snapshot is retained per run. These are estimates, not billing receipts. [Official pricing](https://api-docs.deepseek.com/quick_start/pricing/).

| Run id | Screenshot | Requests | Prompt | Cache hit | Cache miss | Completion | Total | Peak USD | Off-peak USD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| [20261021T185946Z-c21c92](run-records/20261021T185946Z-c21c92/run.json) | city-production__de__2400x1080__probe-clean__1271045.png | 1 | 1836 | 0 | 1836 | 63 | 1899 | 0.0006264 | 0.00031320 |
| [20261021T185948Z-4ba077](run-records/20261021T185948Z-4ba077/run.json) | city-production__de__2400x1080__probe-clean__1271045.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
| [20261021T185950Z-bbbee4](run-records/20261021T185950Z-bbbee4/run.json) | tech-picker__de__2400x1080__probe-clean__1271045.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T185953Z-6b3140](run-records/20261021T185953Z-6b3140/run.json) | tech-picker__de__2400x1080__probe-clean__1271045.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
| [20261021T185955Z-e3cd99](run-records/20261021T185955Z-e3cd99/run.json) | city-production__en__2400x1080__probe-clean__1271045.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T185957Z-cbf5a7](run-records/20261021T185957Z-cbf5a7/run.json) | city-production__en__2400x1080__probe-clean__1271045.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
| [20261021T190000Z-d845c8](run-records/20261021T190000Z-d845c8/run.json) | tech-picker__en__2400x1080__probe-clean__1271045.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T190002Z-c1ff72](run-records/20261021T190002Z-c1ff72/run.json) | tech-picker__en__2400x1080__probe-clean__1271045.png | 1 | 1836 | 1664 | 172 | 27 | 1863 | 0.000093984 | 0.0000469920 |
| [20261021T191152Z-72ce18](run-records/20261021T191152Z-72ce18/run.json) | tech-picker__de__2400x1080__probe-overflow-turns__1271451.png | 1 | 1836 | 0 | 1836 | 406 | 2242 | 0.001038 | 0.0005190 |
| [20261021T191155Z-17b6ce](run-records/20261021T191155Z-17b6ce/run.json) | tech-picker__de__2400x1080__probe-overflow-turns__1271451.png | 1 | 1836 | 1664 | 172 | 447 | 2283 | 0.000597984 | 0.0002989920 |
| [20261021T191158Z-913f4c](run-records/20261021T191158Z-913f4c/run.json) | tech-picker__en__2400x1080__probe-overflow-turns__1271451.png | 1 | 1836 | 0 | 1836 | 165 | 2001 | 0.0007488 | 0.00037440 |
| [20261021T191204Z-2cd54a](run-records/20261021T191204Z-2cd54a/run.json) | tech-picker__en__2400x1080__probe-overflow-turns__1271451.png | 1 | 1836 | 1664 | 172 | 145 | 1981 | 0.000235584 | 0.0001177920 |
| [20261021T191708Z-c9f170](run-records/20261021T191708Z-c9f170/run.json) | city-production__de__2400x1080__probe-overflow-worker__1271452.png | 1 | 1836 | 0 | 1836 | 77 | 1913 | 0.0006432 | 0.00032160 |
| [20261021T191710Z-11f2ef](run-records/20261021T191710Z-11f2ef/run.json) | city-production__de__2400x1080__probe-overflow-worker__1271452.png | 1 | 1836 | 1664 | 172 | 77 | 1913 | 0.000153984 | 0.0000769920 |
| [20261021T191712Z-44af22](run-records/20261021T191712Z-44af22/run.json) | city-production__en__2400x1080__probe-overflow-worker__1271452.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T191714Z-e425ce](run-records/20261021T191714Z-e425ce/run.json) | city-production__en__2400x1080__probe-overflow-worker__1271452.png | 1 | 1836 | 1664 | 172 | 63 | 1899 | 0.000137184 | 0.0000685920 |
| [20261021T191932Z-d9ffa2](run-records/20261021T191932Z-d9ffa2/run.json) | tech-picker__de__2400x1080__probe-wrong-language-fallback__1271453.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T191934Z-724fbb](run-records/20261021T191934Z-724fbb/run.json) | tech-picker__de__2400x1080__probe-wrong-language-fallback__1271453.png | 1 | 1836 | 1664 | 172 | 27 | 1863 | 0.000093984 | 0.0000469920 |
| [20261021T192106Z-be2cea](run-records/20261021T192106Z-be2cea/run.json) | city-production__de__2400x1080__probe-wrong-language-foreign__1271454.png | 1 | 1836 | 0 | 1836 | 160 | 1996 | 0.0007428 | 0.00037140 |
| [20261021T192108Z-23a082](run-records/20261021T192108Z-23a082/run.json) | city-production__de__2400x1080__probe-wrong-language-foreign__1271454.png | 1 | 1836 | 1664 | 172 | 160 | 1996 | 0.000253584 | 0.0001267920 |
| [20261021T192110Z-eca08b](run-records/20261021T192110Z-eca08b/run.json) | city-production__en__2400x1080__probe-wrong-language-foreign__1271454.png | 1 | 1836 | 0 | 1836 | 156 | 1992 | 0.000738 | 0.0003690 |
| [20261021T192113Z-9ed206](run-records/20261021T192113Z-9ed206/run.json) | city-production__en__2400x1080__probe-wrong-language-foreign__1271454.png | 1 | 1836 | 1664 | 172 | 156 | 1992 | 0.000248784 | 0.0001243920 |
| [20261021T192526Z-a462f9](run-records/20261021T192526Z-a462f9/run.json) | tech-picker__de__2400x1080__probe-placeholder-tech__1271455.png | 1 | 1836 | 0 | 1836 | 27 | 1863 | 0.0005832 | 0.00029160 |
| [20261021T192529Z-130955](run-records/20261021T192529Z-130955/run.json) | tech-picker__de__2400x1080__probe-placeholder-tech__1271455.png | 1 | 1836 | 1664 | 172 | 27 | 1863 | 0.000093984 | 0.0000469920 |
| [20261021T192531Z-7bb89c](run-records/20261021T192531Z-7bb89c/run.json) | tech-picker__en__2400x1080__probe-placeholder-tech__1271455.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T192533Z-1179ee](run-records/20261021T192533Z-1179ee/run.json) | tech-picker__en__2400x1080__probe-placeholder-tech__1271455.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
| [20261021T193656Z-4395d8](run-records/20261021T193656Z-4395d8/run.json) | city-production__de__2400x1080__probe-placeholder-city__1271456.png | 1 | 1836 | 0 | 1836 | 119 | 1955 | 0.0006936 | 0.00034680 |
| [20261021T193658Z-52cb3a](run-records/20261021T193658Z-52cb3a/run.json) | city-production__de__2400x1080__probe-placeholder-city__1271456.png | 1 | 1836 | 1664 | 172 | 119 | 1955 | 0.000204384 | 0.0001021920 |
| [20261021T193700Z-68873e](run-records/20261021T193700Z-68873e/run.json) | city-production__en__2400x1080__probe-placeholder-city__1271456.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T193702Z-8dbcb6](run-records/20261021T193702Z-8dbcb6/run.json) | city-production__en__2400x1080__probe-placeholder-city__1271456.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
| [20261021T194040Z-e60d0f](run-records/20261021T194040Z-e60d0f/run.json) | tech-picker__de__2400x1080__probe-truncation-mining__1271457.png | 1 | 1836 | 0 | 1836 | 58 | 1894 | 0.0006204 | 0.00031020 |
| [20261021T194043Z-772638](run-records/20261021T194043Z-772638/run.json) | tech-picker__de__2400x1080__probe-truncation-mining__1271457.png | 1 | 1836 | 1664 | 172 | 69 | 1905 | 0.000144384 | 0.0000721920 |
| [20261021T194044Z-5800a2](run-records/20261021T194044Z-5800a2/run.json) | tech-picker__en__2400x1080__probe-truncation-mining__1271457.png | 1 | 1836 | 0 | 1836 | 68 | 1904 | 0.0006324 | 0.00031620 |
| [20261021T194047Z-e39bbe](run-records/20261021T194047Z-e39bbe/run.json) | tech-picker__en__2400x1080__probe-truncation-mining__1271457.png | 1 | 1836 | 1664 | 172 | 57 | 1893 | 0.000129984 | 0.0000649920 |
| [20261021T194220Z-cfcd3b](run-records/20261021T194220Z-cfcd3b/run.json) | tech-picker__de__2400x1080__probe-small-text-tech__1271458.png | 1 | 1836 | 0 | 1836 | 27 | 1863 | 0.0005832 | 0.00029160 |
| [20261021T194222Z-e17536](run-records/20261021T194222Z-e17536/run.json) | tech-picker__de__2400x1080__probe-small-text-tech__1271458.png | 1 | 1836 | 1664 | 172 | 27 | 1863 | 0.000093984 | 0.0000469920 |
| [20261021T194224Z-e02c81](run-records/20261021T194224Z-e02c81/run.json) | tech-picker__en__2400x1080__probe-small-text-tech__1271458.png | 1 | 1836 | 0 | 1836 | 30 | 1866 | 0.0005868 | 0.00029340 |
| [20261021T194226Z-1f0332](run-records/20261021T194226Z-1f0332/run.json) | tech-picker__en__2400x1080__probe-small-text-tech__1271458.png | 1 | 1836 | 1664 | 172 | 30 | 1866 | 0.000097584 | 0.0000487920 |
