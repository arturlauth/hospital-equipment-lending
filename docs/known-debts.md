# Known debts

Deliberate shortcuts, to be refactored later:

1. **No out-of-service state.** `Equipment` has no status; broken or in-repair items show as
   available in the public catalog.
2. **Free-text category.** `Equipment.category` is a plain `CharField`; spelling variants
   ("Cadeira de rodas" / "cadeira de rodas") appear as separate groups in the catalog.
3. **Catalog lives in `inventory`.** `inventory` now calls `lending.services` while `lending`
   points at `inventory` through its FK. Move the page to a `catalog` app at the second public
   page or the second cross-app need.
