# Mandatory Formulas — Microsoft Word Equation Editor

**Supporting material for the academic report.** Reproduce each expression in Word using **Insert → Equation** (not screenshots).  
In Word 365, you can type **Alt + =** and paste the **Linear LaTeX** column where supported, then press Space to render.

| # | Concept | Linear LaTeX (Word-compatible) |
|---|---------|--------------------------------|
| 1 | Portfolio expected return | `E(r_p)=\sum_{i=1}^{n} w_i \mu_i = \mathbf{w}^{\mathrm{T}}\boldsymbol{\mu}` |
| 2 | Portfolio variance | `\sigma_p^2=\sum_{i=1}^{n}\sum_{j=1}^{n} w_i w_j \sigma_{ij}=\mathbf{w}^{\mathrm{T}}\boldsymbol{\Sigma}\mathbf{w}` |
| 3 | GMVP weights | `\mathbf{w}_{\mathrm{GMVP}}=\frac{\boldsymbol{\Sigma}^{-1}\mathbf{1}}{\mathbf{1}^{\mathrm{T}}\boldsymbol{\Sigma}^{-1}\mathbf{1}}` |
| 4 | Mean-variance utility | `U(\mathbf{w})=E(r_p)-\frac{1}{2} A \sigma_p^2` |
| 5 | Sharpe ratio | `S_p=\frac{E(r_p)-r_f}{\sigma_p}` |

**Symbols:** \(n=10\) assets; \(\mathbf{w}\) weights; \(\boldsymbol{\mu}\) mean returns; \(\boldsymbol{\Sigma}\) covariance; \(A\) risk aversion; \(r_f=0.03\).
