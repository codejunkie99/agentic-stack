# Dynamic Styles

Use this file when the user wants a different visual treatment for a documented pattern, when a client template should prefer specific variants, or when new style variants are being added to the skill.

## Public API

```python
from pattern_variants import render_pattern, list_variants, get_variant_info, clear_cache

variants = list_variants("flywheel")
info = get_variant_info("flywheel", "concentric_rings")

deck.set_pattern_variant("flywheel", "concentric_rings")
deck.set_pattern_variants({
    "kpi": "big_number_dashboard",
    "split_panel": "green_highlight_insights",
})
```

`render_pattern(...)` remains the canonical renderer. Variant selection only changes presentation within the same semantic pattern family. Do not use variants to bypass the routing contract or to change the slide's argument structure.

## Resolution Order

`render_pattern(...)` resolves variants in this order:

1. explicit `variant=...` passed to `render_pattern(...)`
2. per-deck overrides set with `deck.set_pattern_variant(...)` or `deck.set_pattern_variants(...)`
3. template-level defaults in `theme_config["pattern_variants"]`
4. the pattern's bundled `index.json` `default_variant`
5. fallback defaults from `styles/_defaults.json` or a persistent override file

If none of those resolve to a variant, the render should fail rather than guessing.

## Client Template Defaults

`.ee4p` ingestion normalizes client templates into the same theme model as BCG default. To make a client template prefer specific pattern treatments, set `pattern_variants` on the template config before saving it:

```python
template["pattern_variants"] = {
    "flywheel": "concentric_rings",
    "kpi": "big_number_dashboard",
}
```

After that, persist the template with `save_template(...)` so the variant defaults are reused whenever that template is selected.

## Persistent Custom Variants

Bundled variants live under `styles/variants/<pattern>/`. Persistent user or workspace variants can also be installed in:

- `/mnt/user-data/deckster-slide-generator/styles/variants/<pattern>/`
- `~/.deckster-slide-generator/styles/variants/<pattern>/`

Each pattern directory must include:

1. `index.json` describing the pattern, default variant, and metadata
2. one or more Python files that expose `render(deck, slide, data, bounds, **kwargs)`

Optional persistent default files:

- `/mnt/user-data/deckster-slide-generator/styles/_defaults.json`
- `~/.deckster-slide-generator/styles/_defaults.json`

Use those only for broad environment defaults. Prefer template-level `pattern_variants` when the choice should travel with a client brand.

## Cache And Audit Rules

- after installing or editing persistent variants, run `clear_cache()` before rendering
- every new pattern directory must have a routing doc that tells the agent when to use it
- every new default or override must preserve the existing semantic contract of the pattern
- add a golden scenario whenever a new variant family changes the default authoring path
