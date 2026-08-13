import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

heights = np.array([1.00,0.90,0.80,0.70,0.60,0.50,0.40,0.30,0.20])
avg_t = np.array([0.49815,0.46764,0.44744,0.41895,0.39157,0.35946,0.32253,0.28578,0.23630])
g_raw = 2*heights/avg_t**2
g_28 = 2*heights/(avg_t-0.0280)**2
g_40 = 2*heights/(avg_t-0.0403)**2

fig, ax = plt.subplots(figsize=(7,4.5), dpi=150)
ax.plot(heights, g_raw, 'o-', label='Uncorrected (naive model)', color='#c0392b')
ax.plot(heights, g_28, 's-', label='Corrected: Δt = 28 ms (regression)', color='#2980b9')
ax.plot(heights, g_40, '^-', label='Corrected: Δt = 40.3 ms (SUVAT)', color='#27ae60')
ax.axhline(9.81, ls='--', color='gray', label='Accepted g = 9.81 m/s²')
ax.set_xlabel('Release height (m)')
ax.set_ylabel('Derived g (m/s²)')
ax.set_title('Per-height derived g, before and after timing correction')
ax.legend(fontsize=8)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig('photogate_correction_followup.png')
