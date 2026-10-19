"""The generic Spirit of the Hamlet guide — one Textual binary, any law.

Loads any frozen artefact set (``ontology.ttl`` schema, ``population.ttl``
seed, ``manifest.yaml`` declarations, compiled ``oracle``) with zero code
changes per law. All rule truth comes from Lean; the guide only reads the
declared hierarchy and calendar, displays the verdict, and sends acts to
``oracle apply`` on the citizen's explicit confirmation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Select, Static

from . import guide as G
from runtime.loader import EcaMismatchError, FrozenSetError, load_artefact_set
from runtime.oracle import OracleRejected
from .worker import AsyncOracle


def _esc(text: object) -> str:
    """Escape Textual markup brackets in dynamic (law-supplied) text."""
    return str(text).replace("[", "\\[").replace("{", "\\{")

CASES = ["cases/mayor-2027", "cases/mayor-quorum", "cases/requisitions"]


class HamletGuideApp(App):
    """Interactive guide through every process the hamlet is running."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        # Non-printable, so inputs never swallow it: quits even while typing.
        Binding("ctrl+q", "quit", "Force quit", show=False),
        Binding("r", "refresh", "Refresh"),
        Binding("y", "confirm", "Confirm act"),
        Binding("n", "cancel", "Cancel act"),
        Binding("c", "command", "Command line"),
    ]

    CSS = """
    #body { height: 1fr; }
    .panel { border: solid green; padding: 1; margin: 1; }
    .warn { color: yellow; }
    .err { color: red; }
    """

    def __init__(self, case_dir: str | Path = "cases/mayor-2027"):
        super().__init__()
        self.case_dir = Path(case_dir)
        self.artefacts = None
        self.oracle: AsyncOracle | None = None
        self.verdict: dict = {}
        self.windows: dict = {}
        self.instances: list[dict] = []
        self.selected_citizen: str | None = None
        self.selected_process: str | None = None
        self.log_entries: list[str] = []
        self.pending_confirm: dict | None = None
        self._pending_citizen: str | None = None
        self.status_message = "starting…"

    # -- layout ----------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="body"):
            with VerticalScroll(classes="panel"):
                yield Static("— Citizen & process —", id="sel_title")
                yield Select([("—", "NONE")], id="citizen_select", allow_blank=False)
                yield Select([("All processes", "ALL")], id="process_select", allow_blank=False)
                yield Static("— Clock (guide's only write) —")
                with Horizontal():
                    yield Input(value="0", id="clock_day", placeholder="day")
                    yield Input(value="0", id="clock_hour", placeholder="hour")
                    yield Button("Advance clock", id="clock_go")
                with Horizontal():
                    yield Button("+1 day", id="clock_day_plus")
                    yield Button("+1 hour", id="clock_hour_plus")
                yield Static("", id="clock_pos")
            with VerticalScroll(classes="panel"):
                yield Static("— Processes & phases —", id="tree_title")
                yield Static("", id="tree")
                yield Static("", id="instances")
                yield Static("", id="phase")
                yield Static("", id="readings")
                yield Static("", id="blocks")
            with VerticalScroll(classes="panel"):
                yield Static("— Duties of the selected citizen —")
                yield Static("", id="duties")
                yield Input(placeholder="duty <n> [param=<1..N|label> …]", id="cmd")
                with Horizontal():
                    yield Button("Confirm act [y]", id="confirm_go", disabled=True)
                    yield Button("Cancel [n]", id="confirm_no", disabled=True)
                yield Static("", id="confirm")
                yield Static("— Log —")
                yield Static("", id="log")
                yield Static("", id="status")
        yield Footer()

    async def on_mount(self) -> None:
        try:
            self.artefacts = load_artefact_set(self.case_dir)
        except (FrozenSetError, Exception) as exc:
            self.status_message = f"refused to load {self.case_dir}: {exc}"
            self.query_one("#status", Static).update(self.status_message)
            return
        self.oracle = AsyncOracle(self.case_dir)
        try:
            oracle_ids = await self.oracle.eca_ids()
        except Exception as exc:
            self.status_message = f"oracle list failed: {exc}"
            self.query_one("#status", Static).update(self.status_message)
            return
        try:
            from runtime.loader import verify_eca_agreement

            verify_eca_agreement(self.artefacts.manifest, oracle_ids)
        except EcaMismatchError as exc:
            self.status_message = f"ECA mismatch: {exc}"
            self.query_one("#status", Static).update(self.status_message)
            return
        self.windows = G.phase_windows(self.artefacts.seed)
        day, hour = self.oracle.clock()
        self.query_one("#clock_day", Input).value = str(day or 0)
        self.query_one("#clock_hour", Input).value = str(hour or 0)
        await self.refresh_verdict()
        self.status_message = f"loaded {self.artefacts.name}"
        self.query_one("#status", Static).update(self.status_message)

    # -- data refresh ----------------------------------------------------
    async def refresh_verdict(self) -> None:
        if self.oracle is None or self.artefacts is None:
            return
        self.verdict = await self.oracle.check()
        graph = self.oracle.client.graph
        self.instances = G.instance_status(graph, self.artefacts.schema)
        self._render_all()

    def _render_all(self) -> None:
        if self.artefacts is None or self.oracle is None:
            return
        if getattr(self, "_rendering", False):
            return
        self._rendering = True
        try:
            self._render_count = getattr(self, "_render_count", 0) + 1
            self._render_all_inner()
        finally:
            self._rendering = False

    def _render_all_inner(self) -> None:
        graph = self.oracle.client.graph
        manifest = self.artefacts.manifest

        # citizens: every Citizen individual, labelled, plus verdict holders
        citizens = set()
        for s in graph.subjects():
            from rdflib import URIRef
            from rdflib.namespace import RDF

            types = list(graph.objects(s, RDF.type))
            if any(str(t).endswith("Citizen") for t in types if isinstance(t, URIRef)):
                citizens.add(str(s))
        for citizen in (self.verdict.get("pending") or {}):
            citizens.add(citizen)
        options = [(G.label_of(graph, c), c) for c in sorted(citizens)]
        try:
            citizen_select = self.query_one("#citizen_select", Select)
        except Exception:
            return  # screen not mounted (e.g. teardown); nothing to render
        def _opt_values(select) -> list:
            # Select.NULL is the blank sentinel Textual manages itself;
            # it is never one of ours, so it never counts as a difference.
            vals = []
            for o in select._options:
                v = o.value if hasattr(o, "value") else o[1]
                if v is None or v is Select.NULL:
                    continue
                vals.append(v)
            return vals

        if _opt_values(citizen_select) != [c for _, c in options]:
            citizen_select.set_options(options or [("—", "NONE")])
        if self.selected_citizen not in {c for _, c in options}:
            self.selected_citizen = options[0][1] if options else None
        if self.selected_citizen:
            try:
                # Assign only on change: Select.value posts Changed
                # unconditionally, and an unconditional write here would
                # ping-pong with on_select_changed forever (100% CPU spin
                # that also starves key bindings).
                if citizen_select.value != self.selected_citizen:
                    citizen_select.value = self.selected_citizen
            except Exception:
                pass

        # processes: every instance, side by side; selection narrows only
        proc_options = [("All processes", "ALL")] + [
            (f"{i['label'] or i['iri'].rsplit('/', 1)[-1]} [{i['status']}]", i["iri"])
            for i in self.instances
        ]
        process_select = self.query_one("#process_select", Select)
        if _opt_values(process_select) != [v for _, v in proc_options]:
            process_select.set_options(proc_options)
        if self.selected_process not in {v for _, v in proc_options}:
            self.selected_process = "ALL"
        try:
            # Same Changed ping-pong guard as the citizen select above.
            if process_select.value != self.selected_process:
                process_select.value = self.selected_process
        except Exception:
            pass

        # tree: declared hierarchy + windows read from artefacts
        tree = G.process_tree(self.artefacts.schema)
        summaries = G.window_summary(self.windows)
        lines = []
        for root, phases in tree.items():
            lines.append(f"[b]{G.label_of(graph, root)}[/b]")
            for phase in phases:
                lines.append(
                    f"  • {G.label_of(graph, phase)} — {summaries.get(phase, 'unscheduled')}"
                )
        self.query_one("#tree", Static).update(_esc("\n".join(lines) or "no processes declared"))

        # instances: initialised | ongoing | finished-with-outcome
        inst_lines = []
        for inst in self.instances:
            extra = f" outcome={inst['outcome']}" if inst.get("outcome") else ""
            if inst["status"] == "initialised":
                extra += " (awaiting its trigger)"
            inst_lines.append(
                f"  • {inst['label'] or inst['iri'].rsplit('/', 1)[-1]} "
                f"[{inst['status']}{extra}]"
            )
        self.query_one("#instances", Static).update(
            _esc("Instances:\n" + ("\n".join(inst_lines) if inst_lines else "  none"))
        )

        # phase: the oracle's reading only
        phase = self.verdict.get("phase")
        day, hour = self.oracle.clock()
        self.query_one("#clock_pos", Static).update(_esc(f"Clock: day {day} hour {hour}"))
        warning = G.phase_disagreement_warning(self.verdict, self.windows, day, hour)
        phase_text = f"Phase (oracle): {phase}"
        if warning:
            phase_text += f"\n{warning}"
        self.query_one("#phase", Static).update(_esc(phase_text))

        # readings via declared templates; would-win stays advisory
        readings = G.render_readings(manifest, self.verdict, graph)
        self.query_one("#readings", Static).update(
            _esc("Readings:\n" + ("\n".join(f"  • {r}" for r in readings) if readings else "  none"))
        )

        # blocks from structured witnesses
        blocks = G.render_blocks(self.verdict, graph)
        self.query_one("#blocks", Static).update(
            _esc("Blocked:\n" + ("\n".join(f"  • {b}" for b in blocks) if blocks else "  nothing blocked"))
        )

        self._render_duties()
        self.query_one("#log", Static).update(
            _esc("\n".join(self.log_entries[-30:]) or "(no acts yet)")
        )

    def _render_duties(self) -> None:
        if self.artefacts is None:
            return
        graph = self.oracle.client.graph
        duties = G.pending_duties(self.verdict, self.artefacts.manifest, graph)
        if self.selected_citizen:
            duties = [d for d in duties if d["citizen"] == self.selected_citizen]
        else:
            duties = []
        if self.selected_process and self.selected_process != "ALL":
            duties = [d for d in duties if d.get("process") == self.selected_process]
        # No priority recommendation: present every duty, let the user choose.
        if not duties:
            self.query_one("#duties", Static).update("No pending duties for this selection.")
            return
        lines = []
        for i, duty in enumerate(duties):
            proc = duty.get("process")
            proc_label = G.label_of(graph, proc) if proc else "—"
            params = ", ".join(
                f"{p['name']}<{'picker' if p.get('source') == 'choices' else 'you'}>"
                for p in duty.get("params") or []
            )
            lines.append(
                f"[{i}] {duty['eca_label']} ({duty['eca']}) [{duty['modality']}] "
                f"on {proc_label} :: {duty['message']} {params}".strip()
            )
            # Choices render as numbered, labelled options — pick by number.
            for p in duty.get("params") or []:
                if p.get("source") != "choices":
                    continue
                offered = (duty.get("choices") or {}).get(p["name"]) or []
                numbered = "  ".join(
                    f"[{k}] {G.label_of(graph, iri)}"
                    for k, iri in enumerate(offered, start=1)
                )
                lines.append(f"    {p['name']}: {numbered or '(no options offered)'}")
        lines.append("Act with e.g. duty 0 candidate=2, then y/Confirm.")
        self.query_one("#duties", Static).update(_esc("\n".join(lines)))
        self._duties_cache = duties
        confirm = self.query_one("#confirm", Static)
        if self.pending_confirm:
            confirm.update(
                _esc(f"Confirm {self.pending_confirm['eca']} {self.pending_confirm}? [y]/Confirm act, [n]/Cancel.")
            )
        else:
            confirm.update("")
        try:
            self.query_one("#confirm_go", Button).disabled = self.pending_confirm is None
            self.query_one("#confirm_no", Button).disabled = self.pending_confirm is None
        except Exception:
            pass

    def _blur(self) -> None:
        """Return focus to the screen so single-letter keys fire as commands.

        Inputs consume every printable key, so leaving focus in one makes
        q/r/y/n/c type text instead of acting. Blur after every completed
        interaction; the c key re-focuses the command line on demand.
        """
        try:
            self.screen.set_focus(None)
        except Exception:
            pass

    # -- commands --------------------------------------------------------
    async def action_refresh(self) -> None:
        """Re-check the verdict (key: r)."""
        await self.refresh_verdict()
        self._blur()

    async def action_confirm(self) -> None:
        """Confirm the pending act (key: y). Nothing happens without one."""
        await self.confirm_act()

    async def action_cancel(self) -> None:
        """Drop the pending act (key: n)."""
        await self.cancel_act()

    def action_command(self) -> None:
        """Focus the command line (key: c)."""
        try:
            self.query_one("#cmd", Input).focus()
        except Exception:
            pass

    # -- events ----------------------------------------------------------
    async def on_select_changed(self, event: Select.Changed) -> None:
        self._select_changed_count = getattr(self, "_select_changed_count", 0) + 1
        if getattr(self, "_rendering", False):
            return
        # The blank sentinel is not a selection.
        if event.value is None or event.value is Select.NULL:
            return
        if event.select.id == "citizen_select":
            self.selected_citizen = str(event.value) if event.value else None
        elif event.select.id == "process_select":
            self.selected_process = str(event.value) if event.value else "ALL"
        self._render_all()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "clock_go":
            await self.advance_clock_from_inputs()
        elif event.button.id == "clock_day_plus":
            await self.nudge_clock(1, 0)
        elif event.button.id == "clock_hour_plus":
            await self.nudge_clock(0, 1)
        elif event.button.id == "confirm_go":
            await self.confirm_act()
        elif event.button.id == "confirm_no":
            await self.cancel_act()

    async def nudge_clock(self, days: int, hours: int) -> None:
        """Step the clock from its current position (guide's only write)."""
        day, hour = self.oracle.clock()
        day, hour = (day or 0) + days, (hour or 0) + hours
        self.oracle.set_clock(day, hour)  # local only; no oracle call
        try:
            self.query_one("#clock_day", Input).value = str(day)
            self.query_one("#clock_hour", Input).value = str(hour)
        except Exception:
            pass
        await self.refresh_verdict()
        self._blur()

    async def advance_clock_from_inputs(self) -> None:
        try:
            day = int(self.query_one("#clock_day", Input).value)
            hour = int(self.query_one("#clock_hour", Input).value)
        except ValueError:
            self.query_one("#status", Static).update("clock needs integer day and hour")
            return
        self.oracle.set_clock(day, hour)  # local only; no oracle call
        await self.refresh_verdict()
        self._blur()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("clock_day", "clock_hour"):
            await self.advance_clock_from_inputs()
            return
        if event.input.id != "cmd":
            return
        text = event.value.strip()
        if not text.startswith("duty "):
            return
        # e.g. "duty 0 candidate=2" — explicit user action, never auto.
        # A bare number fills the duty's choices params in order ("duty 0 2").
        rest = text[len("duty "):].split()
        try:
            duty = self._duties_cache[int(rest[0])]
        except (ValueError, IndexError, AttributeError):
            self.query_one("#status", Static).update("unknown duty; see list above")
            return
        overrides, positionals = {}, []
        for token in rest[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                overrides[key.strip()] = value.strip()
            else:
                positionals.append(token.strip())
        await self.request_act(duty, overrides, positionals)

    def _resolve_choice(self, duty: dict, name: str, ref: str) -> str | None:
        """Resolve a choices reference to the IRI the oracle expects.

        Accepts a 1-based number as displayed, the full IRI (back-compat),
        or the option's label. Returns None and reports when unresolvable.
        """
        options = (duty.get("choices") or {}).get(name) or []
        graph = self.oracle.client.graph
        ref = str(ref).strip()
        if ref.isdigit():
            index = int(ref)
            if 1 <= index <= len(options):
                return options[index - 1]
        elif ref in options:
            return ref
        else:
            matches = [iri for iri in options
                       if G.label_of(graph, iri).lower() == ref.lower()]
            if len(matches) == 1:
                return matches[0]
        self.query_one("#status", Static).update(
            _esc(f"{duty['eca']}.{name}: pick one of "
                 + ", ".join(f"{k}={G.label_of(graph, iri)}"
                             for k, iri in enumerate(options, start=1)))
        )
        return None

    async def request_act(self, duty: dict, overrides: dict,
                          positionals: list | None = None) -> None:
        decl = self.artefacts.ecas_by_id.get(duty["eca"], {})
        act: dict = {"eca": duty["eca"]}
        positionals = list(positionals or [])
        for param in decl.get("params") or []:
            name = param["name"]
            if name in overrides:
                resolved = self._resolve_choice(duty, name, overrides[name])
                if resolved is None and param.get("source") == "choices":
                    return
                act[name] = resolved if param.get("source") == "choices" else overrides[name]
            elif param.get("source") == "selected":
                act[name] = duty["citizen"]
            else:
                options = (duty.get("choices") or {}).get(name) or []
                if not options:
                    self.query_one("#status", Static).update(
                        f"{duty['eca']}.{name} needs a choice but the verdict offered none"
                    )
                    return
                if positionals:
                    resolved = self._resolve_choice(duty, name, positionals.pop(0))
                    if resolved is None:
                        return
                    act[name] = resolved
                elif len(options) == 1:
                    act[name] = options[0]
                else:
                    # Never silently pick for the citizen when several
                    # options exist: ask for an explicit number instead.
                    self.query_one("#status", Static).update(
                        _esc(f"{duty['eca']}.{name} needs a pick: "
                             + ", ".join(f"{k}={G.label_of(self.oracle.client.graph, iri)}"
                                         for k, iri in enumerate(options, start=1)))
                    )
                    return
        self.pending_confirm = act
        self._pending_citizen = duty.get("citizen")
        self._render_duties()
        self.query_one("#status", Static).update(
            _esc(f"awaiting explicit confirmation for {act['eca']} — [y]/Confirm act, [n]/Cancel")
        )
        # Move focus off the command line so y/n fire as keys; Enter on the
        # focused Confirm button confirms without touching the mouse.
        try:
            self.query_one("#confirm_go", Button).focus()
        except Exception:
            pass

    async def confirm_act(self) -> None:
        """Perform the pending act only on explicit confirmation."""
        if not self.pending_confirm:
            return
        act = self.pending_confirm
        citizen = self._pending_citizen
        self.pending_confirm = None
        self._pending_citizen = None
        decl = (self.artefacts.ecas_by_id or {}).get(act.get("eca"), {})
        try:
            await self.oracle.apply(act)
        except OracleRejected as exc:
            # Rejected act leaves the graph unchanged; report the named reason.
            self.query_one("#status", Static).update(_esc(f"rejected: {exc}"))
            await self.refresh_verdict()
            return
        graph = self.oracle.client.graph
        who = G.label_of(graph, citizen) if citizen else "?"
        params = ", ".join(
            f"{key}={G.label_of(graph, value)}"
            for key, value in act.items() if key != "eca"
        )
        line = f"{decl.get('label', act.get('eca'))} confirmed by {who}"
        if params:
            line += f" ({params})"
        self.log_entries.append(line)
        await self.refresh_verdict()
        # Narrate the outcome in plain terms: the readings the oracle now
        # reports (winner, counts) and who still owes a duty, if anyone.
        graph = self.oracle.client.graph
        readings = G.render_readings(self.artefacts.manifest, self.verdict, graph)
        holders = sorted({
            G.label_of(graph, holder)
            for holder in (self.verdict.get("pending") or {})
        })
        bits = []
        if readings:
            bits.append("Result — " + "; ".join(readings))
        bits.append("awaiting: " + ", ".join(holders) if holders else "nothing pending")
        self.query_one("#status", Static).update(_esc(" · ".join(bits)))
        self._blur()

    async def cancel_act(self) -> None:
        self.pending_confirm = None
        self._pending_citizen = None
        self._render_duties()
        self._blur()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Spirit of the Hamlet guide")
    parser.add_argument("case", nargs="?", default="cases/mayor-2027")
    args = parser.parse_args(argv)
    HamletGuideApp(case_dir=args.case).run()


if __name__ == "__main__":
    main()
