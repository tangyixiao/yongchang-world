"""Regressions for actual Zhuz fragmentation, land gains, and designed flags."""
import hashlib,json,re,unittest
from pathlib import Path
from PIL import Image
from tools.build_state_history import balanced_end,extract_groups,state_blocks
from tools.ownership_topology import component_sizes
ROOT=Path(__file__).resolve().parents[1]; MOD=ROOT/'yongchang_world'
GAME=Path('E:/SteamLibrary/steamapps/common/Victoria 3/game')

class BorderRefinementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((ROOT/'data/scenario/border_refinement.json').read_text('utf-8'))
        base=json.loads((ROOT/'data/baseline/vic3-1.13.11.json').read_text('utf-8'))
        cls.groups={s:extract_groups(b) for s,b in state_blocks((MOD/'common/history/states/00_states.txt').read_text('utf-8-sig'),base).items()}
        cls.owners={}
        for gs in cls.groups.values():
            for g in gs:cls.owners.setdefault(g['owner'],set()).update(g['owned_provinces'])
        geometry=json.loads((ROOT/'.workbuddy/geographic-anchors-20261001.json').read_text('utf-8'))
        cls.adj={p:set(ns) for p,ns in geometry['adjacency'].items()}

    def test_each_zhuz_has_multiple_separate_starting_polities(self):
        for zhuz,tags in self.manifest['zhuz_groups'].items():
            self.assertGreaterEqual(len(tags),3,zhuz)
            for tag in tags:self.assertTrue(self.owners[tag],tag)
        self.assertEqual(len(self.manifest['new_tags']),6)

    def test_russian_acquisitions_are_substantial_and_really_leave_russia(self):
        previous=json.loads((ROOT/'.workbuddy/border-refinement-20261001/data/scenario/ownership_overrides.json').read_text('utf-8'))
        old={r['state']:r['groups'] for r in previous['states']}
        base=json.loads((ROOT/'data/baseline/vic3-1.13.11.json').read_text('utf-8'))
        all_gain=set().union(*(set(ps) for ps in self.manifest['russian_land_acquired'].values()))
        self.assertGreaterEqual(len(all_gain),80)
        kazakh=set().union(*(self.owners[t] for ts in self.manifest['zhuz_groups'].values() for t in ts))
        northeast={'STATE_YAKUTSK','STATE_OKHOTSK'}
        northeast_polities=set().union(*(self.owners[t] for t in ['AMR','SOL','HUL']))
        kazakh_gain=set()
        for s,ps in self.manifest['russian_land_acquired'].items():
            gs=old.get(s,[{'owner':g['country'],'owned_provinces':g['owned_provinces']} for g in base['states'][s]])
            rus=set(next(g['owned_provinces'] for g in gs if g['owner']=='RUS'))
            self.assertTrue(set(ps)<=rus,s)
            if s in northeast:self.assertTrue(set(ps)<=northeast_polities,s)
            else:
                self.assertTrue(set(ps)<=kazakh,s)
                kazakh_gain.update(ps)
        self.assertGreaterEqual(len(kazakh_gain),80)
        self.assertFalse(all_gain&self.owners['RUS'])
        old_rus=set().union(*(set(g['owned_provinces']) for row in old.values() for g in row if g['owner']=='RUS'))
        old_rus.update(p for state,groups in base['states'].items() if state not in old for g in groups if g['country']=='RUS' for p in g['owned_provinces'])
        self.assertLessEqual(len(component_sizes(self.owners['RUS'],self.adj)),len(component_sizes(old_rus,self.adj)),
                             'frontier acquisition must not create new Russian land enclaves')

    def test_changed_frontier_countries_have_no_detached_mainland_pockets(self):
        tags=set(self.manifest['new_tags'])|{'KZH','OZH','UZH','BKY','KHQ','HUL','SOL','ODS','CHR','TSK','KOK','KIR','BUK','KHI','TRM','MEV','TKK','YMD','SMR','KRS','KGL','HSR','SHB','DRZ','QRT'}
        for tag in tags:
            ps=self.owners[tag]
            self.assertEqual(component_sizes(ps,self.adj),[len(ps)],tag)
        self.assertNotIn('KOK',{g['owner'] for g in self.groups['STATE_SYRDARYA']})
        self.assertNotIn('KHI',{g['owner'] for g in self.groups['STATE_MERZ']})

    def test_subjects_have_distinct_levels_instead_of_all_tributaries(self):
        text=(MOD/'common/history/diplomacy/ywc_geographic_diplomacy.txt').read_text('utf-8-sig')
        for tag in ['HXI','DLI','LXJ','CHR','TSK','SMR','KRS','HSR']:
            self.assertRegex(text,rf'country\s*=\s*c:{tag}\s+type\s*=\s*vassal')
        for tag in ['ODS','AMD','KGL']:
            self.assertRegex(text,rf'country\s*=\s*c:{tag}\s+type\s*=\s*tributary')
        self.assertRegex(text,r'country\s*=\s*c:BKY\s+type\s*=\s*protectorate')

class FrontierFlagDesignTest(unittest.TestCase):
    EXCLUDED={'HMI','TRF','KUC','AKS','KSH','YRK','KHT'}
    NATIVE_MAJOR={'CHI','RUS','MGL','PER','JAP'}

    @staticmethod
    def country_block(text, tag):
        matches=list(re.finditer(r'(?m)^'+re.escape(tag)+r'\s*=\s*\{',text))
        if len(matches)!=1:raise AssertionError(f'{tag}: expected one country flag block, got {len(matches)}')
        m=matches[0];opening=text.index('{',m.start(),m.end())
        return text[m.start():balanced_end(text,opening)+1]

    @staticmethod
    def definitions(block):
        result={}
        for m in re.finditer(r'flag_definition\s*=\s*\{',block):
            opening=block.index('{',m.start(),m.end());end=balanced_end(block,opening)+1
            body=block[m.start():end]
            coa=re.search(r'\bcoa\s*=\s*([A-Za-z0-9_]+)',body)
            if coa:result.setdefault(coa.group(1),[]).append(body)
        return result

    def test_imported_base_flags_are_unique_real_png_and_native_dds_assets(self):
        catalog=json.loads((ROOT/'data/scenario/frontier_flag_designs.json').read_text('utf-8-sig'))
        self.assertEqual(len(catalog['flags']),43)
        self.assertEqual(set(catalog['excluded_tags']),self.EXCLUDED)
        self.assertEqual(catalog['deferred_tags'],[])
        self.assertEqual(catalog['status'],'imported_reviewed')
        self.assertEqual(catalog['image_generation']['provider'],'OpenAI Codex built-in image_gen')
        self.assertIsNone(catalog['image_generation']['model_version'])
        self.assertEqual(catalog['image_generation']['generated_source_date'],'2026-10-01')
        png_hashes=set();path_names=set()
        for flag in catalog['flags']:
            tag=flag['tag'];png=ROOT/flag['image_path'];dds=MOD/flag['texture_path'];source=ROOT/flag['source_image']
            self.assertTrue(png.is_file(),tag);self.assertTrue(dds.is_file(),tag);self.assertTrue(source.is_file(),tag)
            digest=hashlib.sha256(png.read_bytes()).hexdigest()
            self.assertEqual(digest,flag['image_sha256'],tag);self.assertNotIn(digest,png_hashes,tag);png_hashes.add(digest)
            self.assertEqual(hashlib.sha256(dds.read_bytes()).hexdigest(),flag['texture_sha256'],tag)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),flag['source_sha256'],tag)
            with dds.open('rb') as stream:self.assertEqual(stream.read(4),b'DDS ',tag)
            header=dds.read_bytes()[:128]
            self.assertEqual(int.from_bytes(header[76:80],'little'),32,tag)
            self.assertEqual(int.from_bytes(header[80:84],'little'),0x41,tag)
            with Image.open(dds) as image:
                self.assertEqual(image.size,(1024,512),tag);self.assertEqual(image.mode,'RGBA',tag)
                self.assertEqual(image.getchannel('A').getextrema(),(255,255),tag)
            self.assertTrue(flag['reason'],tag);self.assertTrue(flag['basis_and_inference'],tag)
            self.assertIn(flag['flag_role'],{'court','military','religious','tribal','localchief'})
            self.assertTrue(flag['sources'],tag)
            self.assertNotIn(str(png.resolve()).casefold(),path_names,tag);path_names.add(str(png.resolve()).casefold())
            self.assertNotIn(str(dds.resolve()).casefold(),path_names,tag);path_names.add(str(dds.resolve()).casefold())
            self.assertEqual(flag['flag_key'],'YWC_'+tag)
        self.assertEqual(len(png_hashes),43)
        self.assertFalse(self.EXCLUDED & {flag['tag'] for flag in catalog['flags']})

    def test_generation_manifest_explicitly_covers_scope_and_variant_cells(self):
        manifest=json.loads((ROOT/'artifacts/automation/frontier_flag_batch_manifest.json').read_text('utf-8-sig'))
        self.assertEqual(set(manifest['excluded_tags']),self.EXCLUDED)
        self.assertEqual(manifest['deferred_tags'],[])
        self.assertEqual(len(manifest['flags']),50)
        self.assertEqual(len(manifest['variant_flags']),22)
        self.assertEqual(sum(bool(x['base_override']) for x in manifest['variant_flags']),3)
        self.assertEqual(len(manifest['variant_batches']),3)
        batches={b['id']:b for b in manifest['variant_batches']}
        self.assertEqual((batches['core_regimes']['columns'],batches['core_regimes']['rows']),(3,4))
        self.assertEqual((batches['sea_regimes']['columns'],batches['sea_regimes']['rows']),(3,3))
        self.assertEqual(batches['core_regimes']['row_edges'],[0,254,499,744,1024])
        self.assertEqual(batches['core_regimes']['column_edges'],[0,512,1023,1536])
        self.assertTrue(batches['core_regimes']['allow_aspect_normalization'])
        self.assertEqual(batches['sea_regimes']['row_edges'],[0,294,585,887])
        self.assertEqual(batches['sea_regimes']['column_edges'],[0,591,1183,1774])
        self.assertEqual(batches['per_socialist_single']['kind'],'single')
        for batch in batches.values():
            self.assertTrue(Path(batch['source_image']).is_file(),batch['id'])
            self.assertTrue((ROOT/batch['source_brief_path']).is_file(),batch['id'])
        cells=[(x['source_batch'],x['source_row'],x['source_column']) for x in manifest['variant_flags']]
        self.assertEqual(len(cells),len(set(cells)))
        self.assertEqual({x['source_cell_label'] for x in manifest['variant_flags'] if x['source_batch']!='per_socialist_single'}.__len__(),21)
        self.assertFalse(self.EXCLUDED & {x['tag'] for x in manifest['variant_flags']})

    def test_final_variant_coas_have_assets_and_political_priorities(self):
        catalog=json.loads((ROOT/'data/scenario/frontier_flag_designs.json').read_text('utf-8-sig'))
        manifest=json.loads((ROOT/'artifacts/automation/frontier_flag_batch_manifest.json').read_text('utf-8-sig'))
        all_assets=catalog['base_overrides']+catalog['variant_flags']
        self.assertEqual(len(catalog['base_overrides']),3)
        self.assertEqual(len(catalog['variant_flags']),19)
        coa_files=list((MOD/'common/coat_of_arms/coat_of_arms').glob('*.txt'))
        coa_text='\n'.join(p.read_text('utf-8-sig') for p in coa_files)
        coa_blocks={}
        for path in coa_files:
            text=path.read_text('utf-8-sig')
            for match in re.finditer(r'(?m)^(YWC_[A-Z]+(?:_[A-Z]+)*)\s*=\s*\{',text):
                opening=text.index('{',match.start(),match.end())
                coa_blocks[match.group(1)]=text[match.start():balanced_end(text,opening)+1]
        for item in all_assets:
            key=item['flag_key'];png=ROOT/item['image_path'];dds=MOD/item['texture_path']
            self.assertTrue(png.is_file(),key);self.assertTrue(dds.is_file(),key)
            self.assertEqual(hashlib.sha256(png.read_bytes()).hexdigest(),item['image_sha256'],key)
            self.assertEqual(hashlib.sha256(dds.read_bytes()).hexdigest(),item['texture_sha256'],key)
            self.assertIn(key,coa_blocks)
            self.assertIn(f'texture = "{item["texture_name"]}"',coa_blocks[key])
            self.assertIn('pattern = "pattern_solid.tga"',coa_blocks[key])
            with Image.open(ROOT/item['source_image']) as source:
                source_crop=source.convert('RGBA').crop(tuple(item['crop_box']))
            with Image.open(png) as actual_crop:
                self.assertEqual(actual_crop.convert('RGBA').tobytes(),source_crop.tobytes(),key)
            with Image.open(png) as opened:
                expected=opened.convert('RGBA').resize((1024,512),Image.Resampling.LANCZOS)
            with Image.open(dds) as imported:
                self.assertEqual(imported.convert('RGBA').tobytes(),expected.tobytes(),key)
        by_key={item['flag_key']:item for item in all_assets}
        self.assertEqual(by_key['YWC_TIB_SECULAR_MONARCHY']['crop_box'],[1,500,511,743])
        self.assertEqual(by_key['YWC_TIB_REPUBLIC']['crop_box'],[513,500,1022,743])
        self.assertEqual(by_key['YWC_TIB_SOCIALIST']['crop_box'],[1024,500,1535,743])
        for key in ('YWC_TIB_SECULAR_MONARCHY','YWC_TIB_REPUBLIC','YWC_TIB_SOCIALIST'):
            self.assertTrue(by_key[key]['aspect_normalized_to_2_1'],key)
        flags=(MOD/'common/flag_definitions/ywc_flags.txt').read_text('utf-8-sig')
        for tag in ('SHU','OIR','JHG','DMG','NQG'):
            block=self.country_block(flags,tag);defs=self.definitions(block)
            self.assertTrue(any('priority = 30' in d and 'coa_def_monarchy_flag_trigger = yes' in d for d in defs['YWC_'+tag]))
            self.assertTrue(any('priority = 30' in d and 'coa_def_theocracy_flag_trigger = yes' in d for d in defs['YWC_'+tag]))
            for regime,priority,trigger in [('REPUBLIC',120,'coa_def_republic_flag_trigger = yes'),('MILITARY_JUNTA',130,'coa_def_military_junta_flag_trigger = yes'),('SOCIALIST',150,'coa_def_communist_flag_trigger = yes')]:
                found=defs['YWC_'+tag+'_'+regime]
                self.assertTrue(any(f'priority = {priority}' in d and trigger in d for d in found),tag+regime)
        native=(MOD/'common/flag_definitions/00_flag_definitions.txt').read_text('utf-8-sig')
        tib=self.definitions(self.country_block(native,'TIB'))
        for key,priority,trigger in [('YWC_TIB',100,'coa_def_theocracy_flag_trigger = yes'),('YWC_TIB_SECULAR_MONARCHY',110,'coa_def_monarchy_flag_trigger = yes'),('YWC_TIB_REPUBLIC',120,'coa_def_republic_flag_trigger = yes'),('YWC_TIB_SOCIALIST',150,'coa_def_communist_flag_trigger = yes')]:
            self.assertTrue(any(f'priority = {priority}' in d and trigger in d for d in tib[key]),key)
        per=self.definitions(self.country_block(native,'PER'))
        self.assertTrue(any('priority = 1501' in d and 'coa_def_communist_flag_trigger = yes' in d for d in per['YWC_PER_SOCIALIST']))
        self.assertNotRegex((MOD/'common/flag_definitions/ywc_flags.txt').read_text('utf-8-sig'),r'(?m)^TIB\s*=')
        self.assertFalse(self.EXCLUDED & {x['tag'] for x in catalog['variant_flags']})

    def test_native_major_flag_definitions_are_preserved_except_scoped_additions(self):
        original=(GAME/'common/flag_definitions/00_flag_definitions.txt').read_text('utf-8-sig')
        modified=(MOD/'common/flag_definitions/00_flag_definitions.txt').read_text('utf-8-sig')
        for tag in ('CHI','RUS','MGL','JAP'):
            self.assertEqual(self.country_block(modified,tag),self.country_block(original,tag),tag)
        native_per=self.definitions(self.country_block(original,'PER'))
        mod_per=self.definitions(self.country_block(modified,'PER'))
        mod_per.pop('YWC_PER_SOCIALIST',None)
        self.assertEqual(mod_per,native_per,'PER native routes changed beyond added socialist route')
        native_tib=self.definitions(self.country_block(original,'TIB'))
        mod_tib=self.definitions(self.country_block(modified,'TIB'))
        for key in ('TIB','TIB_monarchy','TIB_republic'):
            self.assertEqual(mod_tib[key],native_tib[key],key)
        self.assertNotIn('MNG',self.NATIVE_MAJOR)

if __name__=='__main__':unittest.main()
