"""Public CLI pipeline driver controls, no Docker/model allocation."""
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import improvement_optional_public_pipeline_control_v1 as driver


class PipelineDriverControls(unittest.TestCase):
    def test_current_review_closure_and_distinct_prospective_namespace(self):
        self.assertEqual(driver.REVIEW.name, 'fresh-optional-runtime-prelaunch-review-v8.json')
        self.assertEqual(driver.BROKER_REVIEW.name, 'fresh-optional-public-broker-review-v6.json')
        self.assertEqual(driver.DRIVER_REVIEW.name, 'fresh-optional-public-pipeline-control-driver-review-v1.json')
        self.assertEqual(driver.FREEZE.name, 'fresh-optional-public-pipeline-controls-freeze-v1.json')

    def test_literal_comment_command_preserves_real_newlines_and_both_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'lib').mkdir()
            for name in ('a','b'):(root/f'lib/{name}.dart').write_text('source\n')
            command=driver.comment_command(['lib/a.dart','lib/b.dart'], "worker's contribution")
            result=subprocess.run(shlex.split(command),cwd=root,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode())
            for name in ('a','b'):
                self.assertEqual((root/f'lib/{name}.dart').read_text(),"source\n\n// worker's contribution\n")

    def test_cli_argv_and_original_success_streams_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'control-probe';folder.mkdir();body={'status':'ok','result':{'exit_code':7}}
            stdout=json.dumps(body).encode()+b'\n'
            response=subprocess.CompletedProcess([],0,stdout,b'original diagnostic\n')
            with patch.object(driver.runtime,'load',return_value={'deadline':time.time()+1200}),patch.object(driver.subprocess,'run',return_value=response) as run:
                value,code=driver.invoke(folder,'root','a'*48,'exec',{'command':'exit 7'})
            self.assertEqual((value,code),(body,0));argv=run.call_args[0][0]
            self.assertIn(str(driver.ROOT/'tools/improvement_optional_broker_v6.py'),argv)
            self.assertEqual(json.loads(argv[-1]),{'command':'exit 7'})
            captures=list((folder/'broker-cli').iterdir());self.assertEqual(len(captures),1)
            self.assertEqual((captures[0]/'stdout').read_bytes(),stdout)
            self.assertEqual((captures[0]/'stderr').read_bytes(),b'original diagnostic\n')

    def test_cli_error_and_timeout_preserve_original_receipts(self):
        for timeout in (False,True):
            with tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp)/'control-probe';folder.mkdir();stdout=b'{"status":"error","type":"ValueError","message":"denied"}\n'
                response=subprocess.CompletedProcess([],1,stdout,b'')
                error=subprocess.TimeoutExpired(['python3'],1200,output=b'partial',stderr=b'original stderr')
                with patch.object(driver.runtime,'load',return_value={'deadline':time.time()+1200}),patch.object(driver.subprocess,'run',side_effect=error if timeout else None,return_value=response):
                    with self.assertRaises(ValueError):driver.invoke(folder,'root','a'*48,'exec',{})
                capture=next((folder/'broker-cli').iterdir());receipt=json.loads((capture/'receipt.json').read_bytes())
                self.assertEqual(receipt['returncode'],124 if timeout else 1)
                self.assertEqual((capture/'stdout').read_bytes(),b'partial' if timeout else stdout)

    def test_conflicting_current_reviews_do_not_mask_first_invalid_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.py';source.write_text('frozen');correct=driver.entity(source)
            files=[]
            for index,pins in enumerate(({str(source):dict(correct,sha256='0'*64)}, {str(source):correct}, {str(source):correct})):
                p=root/f'review{index}.json';p.write_text(json.dumps({'verdict':'pass','issues':[],'source_entities':pins}));files.append(p)
            with patch.object(driver,'REVIEW',files[0]),patch.object(driver,'DRIVER_REVIEW',files[1]),patch.object(driver,'BROKER_REVIEW',files[2]):
                with self.assertRaises(ValueError):driver.freeze()


if __name__=='__main__':unittest.main()
