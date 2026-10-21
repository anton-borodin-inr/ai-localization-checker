# Per-image OCR runtime

Observed seconds on the recorded host, not an isolated hardware benchmark.
The operation covers preprocessing, recognition, adaptation and local validation/IPC overhead,
minus the separately recorded EasyOCR Reader initialization. Tesseract subprocess setup
remains included in its operation. Downloads are excluded. EasyOCR uses one CPU thread;
Tesseract keeps its existing runtime defaults. Original complete baseline latency is also
retained in each labelled run.json.

| Config | Pass | Image | OCR operation seconds | Reader initialization seconds | Status |
| --- | --- | --- | --- | --- | --- |
| T0 | 1 | tech-picker__de__2400x1080__clean__1271001.png | 0.983 | 0.000 | checked |
| T0 | 1 | tech-picker__de__2400x1080__injected__1271002.png | 0.832 | 0.000 | checked |
| T0 | 1 | tech-picker__en__2400x1080__clean__1271001.png | 0.480 | 0.000 | checked |
| T0 | 1 | city-production__de__2400x1080__clean__1271045.png | 0.639 | 0.000 | checked |
| T0 | 1 | city-production__en__2400x1080__clean__1271045.png | 0.408 | 0.000 | checked |
| T0 | 1 | tech-picker__de__2400x1080__clean__1271045.png | 1.010 | 0.000 | checked |
| T0 | 1 | tech-picker__en__2400x1080__clean__1271045.png | 0.595 | 0.000 | checked |
| T0 | 2 | tech-picker__de__2400x1080__clean__1271001.png | 0.807 | 0.000 | checked |
| T0 | 2 | tech-picker__de__2400x1080__injected__1271002.png | 0.794 | 0.000 | checked |
| T0 | 2 | tech-picker__en__2400x1080__clean__1271001.png | 0.473 | 0.000 | checked |
| T0 | 2 | city-production__de__2400x1080__clean__1271045.png | 0.628 | 0.000 | checked |
| T0 | 2 | city-production__en__2400x1080__clean__1271045.png | 0.409 | 0.000 | checked |
| T0 | 2 | tech-picker__de__2400x1080__clean__1271045.png | 0.961 | 0.000 | checked |
| T0 | 2 | tech-picker__en__2400x1080__clean__1271045.png | 0.598 | 0.000 | checked |
| T1 | 1 | tech-picker__de__2400x1080__clean__1271001.png | 1.582 | 0.000 | checked |
| T1 | 1 | tech-picker__de__2400x1080__injected__1271002.png | 1.492 | 0.000 | checked |
| T1 | 1 | tech-picker__en__2400x1080__clean__1271001.png | 1.103 | 0.000 | checked |
| T1 | 1 | city-production__de__2400x1080__clean__1271045.png | 1.376 | 0.000 | checked |
| T1 | 1 | city-production__en__2400x1080__clean__1271045.png | 1.023 | 0.000 | checked |
| T1 | 1 | tech-picker__de__2400x1080__clean__1271045.png | 1.886 | 0.000 | checked |
| T1 | 1 | tech-picker__en__2400x1080__clean__1271045.png | 1.252 | 0.000 | checked |
| T1 | 2 | tech-picker__de__2400x1080__clean__1271001.png | 1.634 | 0.000 | checked |
| T1 | 2 | tech-picker__de__2400x1080__injected__1271002.png | 1.601 | 0.000 | checked |
| T1 | 2 | tech-picker__en__2400x1080__clean__1271001.png | 1.166 | 0.000 | checked |
| T1 | 2 | city-production__de__2400x1080__clean__1271045.png | 1.403 | 0.000 | checked |
| T1 | 2 | city-production__en__2400x1080__clean__1271045.png | 1.033 | 0.000 | checked |
| T1 | 2 | tech-picker__de__2400x1080__clean__1271045.png | 1.809 | 0.000 | checked |
| T1 | 2 | tech-picker__en__2400x1080__clean__1271045.png | 1.220 | 0.000 | checked |
| T2 | 1 | tech-picker__de__2400x1080__clean__1271001.png | 1.229 | 0.000 | checked |
| T2 | 1 | tech-picker__de__2400x1080__injected__1271002.png | 1.095 | 0.000 | checked |
| T2 | 1 | tech-picker__en__2400x1080__clean__1271001.png | 0.791 | 0.000 | checked |
| T2 | 1 | city-production__de__2400x1080__clean__1271045.png | 0.870 | 0.000 | checked |
| T2 | 1 | city-production__en__2400x1080__clean__1271045.png | 0.632 | 0.000 | checked |
| T2 | 1 | tech-picker__de__2400x1080__clean__1271045.png | 1.350 | 0.000 | checked |
| T2 | 1 | tech-picker__en__2400x1080__clean__1271045.png | 1.360 | 0.000 | checked |
| T2 | 2 | tech-picker__de__2400x1080__clean__1271001.png | 1.271 | 0.000 | checked |
| T2 | 2 | tech-picker__de__2400x1080__injected__1271002.png | 1.153 | 0.000 | checked |
| T2 | 2 | tech-picker__en__2400x1080__clean__1271001.png | 0.819 | 0.000 | checked |
| T2 | 2 | city-production__de__2400x1080__clean__1271045.png | 0.874 | 0.000 | checked |
| T2 | 2 | city-production__en__2400x1080__clean__1271045.png | 0.636 | 0.000 | checked |
| T2 | 2 | tech-picker__de__2400x1080__clean__1271045.png | 1.365 | 0.000 | checked |
| T2 | 2 | tech-picker__en__2400x1080__clean__1271045.png | 0.990 | 0.000 | checked |
| E0 | 1 | tech-picker__de__2400x1080__clean__1271001.png | 8.555 | 6.501 | checked |
| E0 | 1 | tech-picker__de__2400x1080__injected__1271002.png | 6.828 | 0.000 | checked |
| E0 | 1 | tech-picker__en__2400x1080__clean__1271001.png | 7.327 | 3.385 | checked |
| E0 | 1 | city-production__de__2400x1080__clean__1271045.png | 6.522 | 0.000 | checked |
| E0 | 1 | city-production__en__2400x1080__clean__1271045.png | 6.262 | 0.000 | checked |
| E0 | 1 | tech-picker__de__2400x1080__clean__1271045.png | 6.288 | 0.000 | checked |
| E0 | 1 | tech-picker__en__2400x1080__clean__1271045.png | 9.224 | 0.000 | checked |
| E0 | 2 | tech-picker__de__2400x1080__clean__1271001.png | 5.994 | 3.564 | checked |
| E0 | 2 | tech-picker__de__2400x1080__injected__1271002.png | 6.957 | 0.000 | checked |
| E0 | 2 | tech-picker__en__2400x1080__clean__1271001.png | 12.007 | 3.546 | checked |
| E0 | 2 | city-production__de__2400x1080__clean__1271045.png | 9.895 | 0.000 | checked |
| E0 | 2 | city-production__en__2400x1080__clean__1271045.png | 9.121 | 0.000 | checked |
| E0 | 2 | tech-picker__de__2400x1080__clean__1271045.png | 8.401 | 0.000 | checked |
| E0 | 2 | tech-picker__en__2400x1080__clean__1271045.png | 9.336 | 0.000 | checked |
| E1 | 1 | tech-picker__de__2400x1080__clean__1271001.png | 41.783 | 3.723 | checked |
| E1 | 1 | tech-picker__de__2400x1080__injected__1271002.png | 38.988 | 0.000 | checked |
| E1 | 1 | tech-picker__en__2400x1080__clean__1271001.png | 37.752 | 3.956 | checked |
| E1 | 1 | city-production__de__2400x1080__clean__1271045.png | 33.228 | 0.000 | checked |
| E1 | 1 | city-production__en__2400x1080__clean__1271045.png | 33.946 | 0.000 | checked |
| E1 | 1 | tech-picker__de__2400x1080__clean__1271045.png | 35.108 | 0.000 | checked |
| E1 | 1 | tech-picker__en__2400x1080__clean__1271045.png | 36.114 | 0.000 | checked |
| E1 | 2 | tech-picker__de__2400x1080__clean__1271001.png | 32.201 | 3.431 | checked |
| E1 | 2 | tech-picker__de__2400x1080__injected__1271002.png | 34.197 | 0.000 | checked |
| E1 | 2 | tech-picker__en__2400x1080__clean__1271001.png | 33.879 | 3.413 | checked |
| E1 | 2 | city-production__de__2400x1080__clean__1271045.png | 38.029 | 0.000 | checked |
| E1 | 2 | city-production__en__2400x1080__clean__1271045.png | 42.084 | 0.000 | checked |
| E1 | 2 | tech-picker__de__2400x1080__clean__1271045.png | 39.375 | 0.000 | checked |
| E1 | 2 | tech-picker__en__2400x1080__clean__1271045.png | 40.370 | 0.000 | checked |
| E2 | 1 | tech-picker__de__2400x1080__clean__1271001.png | 37.322 | 3.696 | checked |
| E2 | 1 | tech-picker__de__2400x1080__injected__1271002.png | 32.070 | 0.000 | checked |
| E2 | 1 | tech-picker__en__2400x1080__clean__1271001.png | 35.238 | 3.454 | checked |
| E2 | 1 | city-production__de__2400x1080__clean__1271045.png | 33.147 | 0.000 | checked |
| E2 | 1 | city-production__en__2400x1080__clean__1271045.png | 31.367 | 0.000 | checked |
| E2 | 1 | tech-picker__de__2400x1080__clean__1271045.png | 32.322 | 0.000 | checked |
| E2 | 1 | tech-picker__en__2400x1080__clean__1271045.png | 32.960 | 0.000 | checked |
| E2 | 2 | tech-picker__de__2400x1080__clean__1271001.png | 36.613 | 4.543 | checked |
| E2 | 2 | tech-picker__de__2400x1080__injected__1271002.png | 33.931 | 0.000 | checked |
| E2 | 2 | tech-picker__en__2400x1080__clean__1271001.png | 34.222 | 3.420 | checked |
| E2 | 2 | city-production__de__2400x1080__clean__1271045.png | 34.843 | 0.000 | checked |
| E2 | 2 | city-production__en__2400x1080__clean__1271045.png | 33.251 | 0.000 | checked |
| E2 | 2 | tech-picker__de__2400x1080__clean__1271045.png | 34.803 | 0.000 | checked |
| E2 | 2 | tech-picker__en__2400x1080__clean__1271045.png | 34.866 | 0.000 | checked |
