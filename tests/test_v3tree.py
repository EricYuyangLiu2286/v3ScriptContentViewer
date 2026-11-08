"""Run: python -m unittest discover -s tests   (from the repository root, with src on the path)."""
import json, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tests'))

import fixtures  # noqa: E402
from v3tree import config as C, ops, judge as J, search as S, i18n  # noqa: E402
from v3tree.clausewitz import parse  # noqa: E402
from v3tree.sources import Sources, layers_from_config, load_loc  # noqa: E402


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.tmp.name)
        cls.cfg = fixtures.config(cls.base)
        i18n.set_lang('en')
        ops.build_index(cls.cfg, verbose=False)
        cls.g = J.load_index(ops.out_dir(cls.cfg))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def edges(self, s=None, t=None):
        return [e for e in self.g['edges'] if (s is None or e['s'] == s) and (t is None or e['t'] == t)]


class TestParse(unittest.TestCase):
    def test_fixture_files_parse(self):
        for files in (fixtures.GAME, fixtures.MOD_A, fixtures.MOD_B):
            for rel, text in files.items():
                if rel.endswith('.txt'):
                    parse(text)


class TestConfig(unittest.TestCase):
    def test_needs_one_path(self):
        code, lines = C.doctor({**C.empty(), 'game': {'path': ''}, 'mods': []}, write_detected=False)
        self.assertEqual(code, 2)

    def test_game_dirs_accepts_root_or_game(self):
        with tempfile.TemporaryDirectory() as d:
            roots = fixtures.write(Path(d))
            self.assertEqual(C.game_dirs(roots['game'])[1], roots['game'] / 'game')
            self.assertEqual(C.game_dirs(roots['game'] / 'game')[1], roots['game'] / 'game')
            self.assertEqual(C.game_dirs(Path(d))[0], None)

    def test_doctor_ok_and_version(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = fixtures.config(Path(d))
            code, lines = C.doctor(cfg)
            self.assertLess(code, 2, lines)
            self.assertEqual(cfg['detected'].get('game_version'), '9.9.9')

    def test_mod_only_is_allowed(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = fixtures.config(Path(d), game=False)
            code, lines = C.doctor(cfg, write_detected=False)
            self.assertLess(code, 2, lines)


class TestSources(Base):
    def test_layer_order(self):
        self.assertEqual([l.id for l in layers_from_config(self.cfg)], ['game', 'mod1', 'mod2'])

    def test_same_path_file_replaced(self):
        src = Sources(layers_from_config(self.cfg))
        files, over = src.collect('common/scripted_effects')
        eff = [f for f in files if f[1].endswith('00_eff.txt')]
        self.assertEqual([f[0] for f in eff], ['mod1'])
        self.assertTrue(any(o['file'].endswith('00_eff.txt') and o['by'] == 'mod1' for o in over))

    def test_localisation_replace_wins(self):
        loc, _ = load_loc(Sources(layers_from_config(self.cfg)), ['english'])
        self.assertEqual(loc['je_root'], 'Root JE (mod A)')


class TestIndex(Base):
    def test_trigger_event_with_line(self):
        es = self.edges('je:je_root', 'event:x.1')
        self.assertTrue(es)
        self.assertEqual(es[0]['line'], 2)

    def test_multiline_block_records_end(self):
        es = self.edges('event:x.2', 'event:x.3')
        self.assertTrue(es)
        self.assertGreater(es[0].get('end', 0), es[0]['line'])
        self.assertIn('5', es[0]['ctx'])         # "after 5 days"

    def test_parameter_resolved_from_caller(self):
        es = self.edges('button:btn_a', 'event:x.2')
        self.assertTrue(es and es[0]['rel'] == 'via_param')
        self.assertEqual(es[0]['root'], 'mod1')   # the effect that holds the line is mod A's copy

    def test_replaced_definition_not_walked(self):
        reads = self.edges('je:je_child', 'var:mod_a_was_here')
        self.assertTrue(reads)                    # REPLACE body is walked

    def test_duplicate_first_wins(self):
        n = self.g['nodes']['event:x.1']
        ignored = [s for s in n['sites'] if s.get('ignored')]
        self.assertEqual(len(ignored), 1)
        self.assertEqual(ignored[0]['root'], 'game')
        self.assertTrue(self.edges('event:x.1', 'gvar:gv_from_mod_b'))
        self.assertFalse(self.edges('event:x.1', 'je:je_child'))

    def test_on_actions_merge(self):
        ev = {e['t'] for e in self.edges('onaction:on_monthly_pulse_country')}
        self.assertTrue({'event:x.3', 'event:x.4'} <= ev)

    def test_pop_moved_through_variable(self):
        es = [e for e in self.edges('seffect:mover') if e['rel'] == 'move_pop_via_var']
        self.assertTrue(any(e['t'] == 'pop:culture:natives' for e in es))

    def test_inline_bar_progress(self):
        self.assertTrue(self.edges('event:x.3', 'bar:bar_a'))

    def test_history_ids_have_no_spaces(self):
        self.assertIn('history:countries/usa_-_usa', self.g['nodes'])
        self.assertFalse([k for k in self.g['nodes'] if any(c.isspace() for c in k)])


class TestCasesAndSearch(Base):
    def test_ai_path_expand_and_render(self):
        od = ops.out_dir(self.cfg)
        J.new_case(od, 'ai', ['je:je_root'], 'test', lang='en')
        with (J.case_dir(od, 'ai') / 'decisions.txt').open('a', encoding='utf-8') as f:
            f.write('in event:x.1 # first event\nboundary gvar:gv_done @Other # other system\n')
        _, case, inc, bnd, jud, pend, cands, conf = J.run_expand(od, ops.case_path(self.cfg, 'ai'), g=self.g, quiet=True)
        self.assertIn('event:x.1', inc)
        self.assertIn('gvar:gv_done', bnd)
        res = ops.render_case(self.cfg, 'ai', self.g)
        self.assertTrue(Path(res['map']).exists())
        self.assertEqual(res['spot_ok'], res['spot_n'])

    def test_step_search_judge_undo_signoff(self):
        od = ops.out_dir(self.cfg)
        cp = J.new_case(od, 'ui', ['je:je_root'], 'test', lang='en', mode='ui')
        case = J.load_case(cp)
        S.search(case, self.g, 1)
        found1 = set(S.state(J.load_case(cp))['found'])
        self.assertIn('event:x.1', found1)
        dp = cp.parent / 'decisions.txt'
        before = dp.read_text('utf-8') if dp.exists() else ''
        S.judge_node(J.load_case(cp), self.g, 'je:je_root', 'out', 'en')   # roots cannot be judged
        self.assertEqual(before, dp.read_text('utf-8') if dp.exists() else '')
        self.assertIn('je:je_root', S.view_nodes(J.load_case(cp), self.g))
        case = J.load_case(cp)
        S.judge_node(case, self.g, 'event:x.1', 'out', 'en')
        self.assertNotIn('event:x.1', S.view_nodes(J.load_case(cp), self.g))
        self.assertTrue(S.undo(J.load_case(cp)))
        self.assertIn('event:x.1', S.view_nodes(J.load_case(cp), self.g))
        S.search(J.load_case(cp), self.g, 3)
        case = S.finalize(J.load_case(cp), self.g, 'en')
        for line in (cp.parent / 'decisions.txt').read_text('utf-8').splitlines():
            if line and not line.startswith('//'):
                self.assertTrue(J.DEC_RE.match(line) or J.RULE_RE.match(line), line)
        res = ops.render_case(self.cfg, 'ui', self.g)
        self.assertGreater(res['in'], 1)

    def test_tag_roots(self):
        self.assertEqual(J.resolve_roots(self.g, 'USA'), [])       # only history writes c:USA, not a JE/event/decision
        self.assertEqual(J.resolve_roots(self.g, 'je_root'), ['je:je_root'])


if __name__ == '__main__':
    unittest.main()
