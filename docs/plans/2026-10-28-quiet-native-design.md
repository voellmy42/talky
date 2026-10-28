# Quiet native Talky

Approved direction: the user approved the quiet native proposal and requested fluid,
dynamic visuals that stay contained and do not distract or overlap other elements.

Use a compact, nonactivating bottom-center capsule above the Dock. Reserve separate
areas for a bounded waveform, status/subtitle and language/Esc badges; use clear
labels as well as color. Audio bars reflect the latest RMS measurement only during
capture. Smooth their attack/release at 30 Hz on the main thread, with a slow bounded
traveling wave for processing. No large glow, bounce, particles or moving window.
Respect Reduce Motion/Reduce Transparency. Stop animation when hidden and reset
levels when capture ends. Success feedback is brief; recoverable errors stay legible.

Provide an explicitly labeled appearance preview with synthetic levels, state
selection and a reduced-motion preview switch. It must work before permission setup,
without opening audio hardware, downloading models, reading selection or pasting.

Group statistics and language in submenus, preserve existing action availability,
and simplify onboarding copy/spacing. Keep the existing mascot as an intentional
rounded artwork tile; generating replacement artwork is outside this change.

Verify the current regression suite, add focused audio-meter lifecycle tests, exercise
native preview transitions, render each state and rebuild/install the verified app.
Live speech remains unavailable on this machine and is not an acceptance claim.
