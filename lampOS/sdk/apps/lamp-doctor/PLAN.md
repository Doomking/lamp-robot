# Lamp Doctor: plan (#8726)

An SDK app that scores how the lamp's conversations go, on the lamp, and
sends only a fixed schema through `log.send`. It holds `turns`,
`conversation`, `model.ask` and `log.send`, and not `net`. English only.

## What the app does, once a day

1. `turns`: read the day's finished-turn records (no words).
2. `score`: from those records alone, compute the numbers, the failure
   categories, the tier (T1 to T4) and a 0 to 100 score. No model, no text.
3. `model.ask` (at most once; the lamp caps it at one a day): with the
   numbers, and with the day's heard words only if `conversation` is held,
   ask the lamp's model which of the **fixed failure categories** it sees.
4. `diagnose`: keep only the categories the answer names. Everything else in
   the answer is dropped, so free text cannot reach step 5.
5. `log.send`: one report of the fixed schema. The lamp refuses any string
   outside the listed categories, so this is checked twice: here, and by the
   lamp.

## Tests first (all in `tests/`, failing until the code exists)

- `test_score.py`: the score from a set of turn records.
- `test_report.py`: the report holds only the fixed fields.
- `test_diagnose.py`: a diagnosis with free text, a heard sentence and a
  name never reaches `log.send`; `model.ask` is called once; if the model
  fails the report still goes without a diagnosis.
- `test_app.py`: the whole day against a fake of Ten's ops; a strict fake
  `log.send` refuses anything outside the schema, and the app never trips it.

## Shapes (Ten's design on #8726, 12:52)

`tests/fake_ops.py` holds them in one place; it is the app's only copy of
lamp-control's side until Ten's ops exist.

- **Grants** (an app's socket only): `turns`, `conversation`, `model`
  (`model.ask`), `report` (`log.send`). Never `net` with `conversation`.
- **`turns`** (`get turns`, event `turns.finished`): one record per turn:
  `turn`, `at` (unix minute), `heard_to_first_sound_ms`, `cut_ins`,
  `calls` = `[{name, ms, timed_out}]` (the lamp's own tool names),
  `outcome` (`answered|stuck|refused|held|asked_again`), `words_heard`,
  `words_said`, `heard_wrongly`, `name_missed`, `held_then_repeated`,
  `route`, `build`. No text, no speaker.
- **`model.ask`**: `{prompt, input}` to the lamp's own provider; 1 call a
  day, prompt at most 2 KiB, input at most 8 KiB, answer at most 1,000
  characters; over the cap it is refused `rate_limited`. Without
  `conversation`, `input` may hold only the `turns` numbers.
- **`log.send`**: the report below, parsed into a closed type; a string
  outside the lists is refused whole (`bad_args`); at most once an hour.
  The lamp fills `build` itself, so the app sends none.
- **The report:** `turns`, `answered_within_5s`,
  `heard_to_first_sound_ms_median`, `heard_to_first_sound_ms_p90`,
  `asked_again`, `held`, `cut_ins`, `tool_timeouts`, `stuck`, `tier`,
  `score` (0 to 100), `failures` = `[{category, count}]`, `route`,
  `diagnosis_version`.
- **Failure categories** (Ten owns the list): `heard_wrongly`,
  `slow_first_sound`, `call_held`, `answer_cut_off`, `tool_timeout`,
  `silent_turn`.

## Open questions

1. `answered_within_5s` is a percent (0 to 100, one decimal) in this app.
   Is that Ten's meaning, or a count?
2. #7452's tier table is not in the repo; `score.DEPTH` is a placeholder
   from tool names to T1 to T4, to be replaced by Backend's.
3. `min_build` is 1 until the first build that carries Ten's ops lands.

## Then

1. Code to make the tests pass (score, report, diagnose, app).
2. `app.json` and `lamp app check` / `pack`.
3. Run it on the virtual lamp (lamp-sim), then on one lamp.
