# Business model

What the lending service does, in business terms. How it is built lives in the code.

## Entities

| Entity | What it is | Key facts |
|---|---|---|
| Equipamento | A physical item lent to the community | Patrimônio (category code + number, never changes), depósito, situação |
| Categoria | Kind of item (andador, cama…) | Its code prefixes the patrimônio |
| Depósito | Where items are kept and picked up | |
| Pessoa | Someone registered by the equipe; never logs in | Acts as Beneficiário (takes the item) or Solidário (vouches, contacted when late) |
| Empréstimo | One item with one Beneficiário and one Solidário | Emprestado em, devolução prevista, devolvido em |
| Equipe | Atendente and Gestor | Gestor also writes items off |

## Equipment situação

| Situação | Can be lent | Public sees it |
|---|---|---|
| Ativo | Yes, if no open loan | Yes |
| Em manutenção | No | Yes, as unavailable |
| Extraviado | No | No |
| Baixado (final) | No | No |

Loan and situação are independent: one says who has the item, the other whether it can go out.

## Processes

1. **Emprestar** — equipe picks a lendable item, a Beneficiário and a different Solidário;
   devolução prevista defaults to six months.
2. **Devolver** — equipe records the date and how it came back: em ordem, com defeito
   (→ em manutenção) or extraviado (→ extraviado).
3. **Corrigir empréstimo** — any equipe member fixes dates or undoes a return, giving a reason;
   undo is impossible once the item went out again.
4. **Mudar situação** — any equipe member, with date and reason. **Dar baixa** is Gestor only and
   never while a loan is open; a lost item is returned as extraviado first.

## Rules

1. One open loan per item; dates never go before the loan start nor into the future.
2. A loan is late when open and past its devolução prevista (due today is not late).
3. Every loan action and every situação change is recorded: who, when, what changed, why.
   Only the Gestor reads these records.
