import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from v3tree.index import build
from v3tree.sources import Layer, Sources
from v3tree import i18n


class CharacterIndexTest(unittest.TestCase):
    def test_scope_provenance_and_lifetime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                'common/character_templates/test.txt': 'p = { first_name = One traits = { brave } }\nq = { first_name = Two }',
                'common/history/characters/state.txt': 'CHARACTERS = { c:ABC = { create_character = { template = p on_created = { set_global_variable = { name = person value = this } } } } }',
                'events/demo.txt': '''demo.1 = {
                    desc = first_desc
                    immediate = { global_var:person = { save_scope_as = guest } }
                    option = { scope:guest = { show_as_tooltip = { kill_character = yes } } }
                }
                demo.2 = {
                    desc = second_desc
                    immediate = { create_character = { template = q save_scope_as = guest } }
                    option = { scope:guest = { transfer_character = ROOT } }
                }
                demo.4 = {
                    immediate = {
                        ordered_character = {
                            limit = { has_template = p }
                            alternative_limit = { has_role_of_type = politician }
                            save_scope_as = publisher
                        }
                    }
                    option = { scope:publisher = { add_modifier = { name = reward } } }
                }
                demo.3 = { immediate = { create_character = { first_name = Three is_admiral = yes } } }
                ''',
                'localization/english/x.yml': """l_english:
 first_desc: "[SCOPE.sCharacter('guest').GetFullName]"
 second_desc: "[SCOPE.sCharacter('guest').GetFullName]"
""",
            }
            for path,body in files.items():
                p = root/path
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text(body,'utf-8')
            i18n.set_lang('en')
            g = build(Sources([Layer('game','game',root,'test')]),verbose=False)
            def matches(a,b):
                return [e for e in g.edges if e['s']==a and e['t']==b]
            first = 'charscope:event:demo.1/guest'
            second = 'charscope:event:demo.2/guest'
            self.assertTrue(matches('history:characters/state','character:p'))
            self.assertTrue(matches('character:p','gvar:person'))
            self.assertTrue(matches('gvar:person',first))
            self.assertEqual(matches(first,'charstate:kill_character=yes')[0]['flags'],['tooltip_only'])
            self.assertFalse(matches(second,'charstate:kill_character=yes'))
            self.assertTrue(matches(second,'charstate:transfer_character=ROOT'))
            self.assertEqual(matches('charloc:first_desc',first)[0]['line'],2)
            self.assertFalse(matches('charloc:first_desc',second))
            choices = [e['s'] for e in g.edges if e['s'].startswith('charselector:event:demo.4/')
                       and e['t']=='character:p' and e['rel']=='candidate_template']
            self.assertEqual(len(choices),1)
            publisher = 'charscope:event:demo.4/publisher'
            self.assertTrue(matches(choices[0],publisher))
            self.assertFalse(matches('character:p',publisher))
            self.assertTrue(matches(publisher,'modifier:reward'))
            self.assertEqual(len([e for e in g.edges if e['rel']=='create_character']),3)

    def test_character_kept_in_variable_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                'common/character_templates/test.txt': 'p = { first_name = One }',
                'common/history/global/start.txt': 'GLOBAL = { c:ABC = { create_character = { template = p on_created = { set_character_busy_and_immortal = yes set_global_variable = { name = person value = this } } } } }',
                'common/scripted_effects/bind.txt': 'bind = { add_to_variable_list = { name = portraits target = global_var:person } }',
                'common/journal_entries/je.txt': '''je_demo = {
                    immediate = { bind = yes }
                    outcome = {
                        trigger = { always = yes }
                        effect = {
                            scope:journal_entry = {
                                every_in_list = {
                                    variable = portraits
                                    set_character_busy_and_immortal = no
                                }
                            }
                        }
                    }
                }''',
            }
            for path,body in files.items():
                p = root/path
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text(body,'utf-8')
            i18n.set_lang('en')
            g = build(Sources([Layer('game','game',root,'test')]),verbose=False)
            def matches(a,b,rel=None):
                return [e for e in g.edges if e['s']==a and e['t']==b and (rel is None or e['rel']==rel)]
            self.assertTrue(matches('gvar:person','var:portraits','add_to_variable_list'))
            release = matches('var:portraits','charstate:set_character_busy_and_immortal=no')
            self.assertTrue(release)
            self.assertEqual(release[0]['line'],9)
