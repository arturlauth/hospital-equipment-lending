# Known debts

Deliberate shortcuts, to be refactored later:

1. **Catalog ignores equipment status.** `Equipment.status` exists, but the public catalog still
   lists damaged and written-off items as available. Fixed with the catalog slice.
2. **Catalog lives in `inventory`.** `inventory` now calls `lending.services` while `lending`
   points at `inventory` through its FK. Move the page to a `catalog` app at the second public
   page or the second cross-app need.
