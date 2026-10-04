# Equipment status and loans

Two independent facts:

| Fact | Question | Values | Changed by |
|---|---|---|---|
| Loan | Who has it now? | open / returned (return date) | lend, return, loan edit |
| Equipment status | Can it go out at all? | active · damaged (shown as "em manutenção" from slice 9) · written off | explicit action on the equipment |

1. Lendable = active and no open loan.
2. Editing a loan never changes the status; changing the status never touches a loan. Undoing a
   return is always allowed; the loan page warns when the equipment is not active.
3. "Voltou com defeito" on return is a shortcut for setting the status to damaged.
4. Write-off is Gestor only and blocked while a loan is open. A lost item is first returned as
   "extraviado", then written off.
5. Every status change is logged: who, when, from/to, reason (slice 9).
6. A late loan is open and past its due date (due today is not late). The Solidário is the contact.
