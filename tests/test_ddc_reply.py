"""Test the native helper's parser against captured hardware replies."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class NativeReplyTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'C compiler required for native parser test')
    def test_captured_packets_and_corruption(self):
        source = r'''
#include <assert.h>
#include "displayshift_reply.h"
int main(void) {
    uint8_t lg[] = {0x6e,0x51,0x02,0,0x60,0,0,0x12,0,0x0f,0xc9,0x2f};
    uint8_t brightness[] = {0x6e,0x51,0x02,0,0x10,0,0,0x64,0,0x55,0x95,0x2f};
    uint8_t aw[] = {0x6e,0x88,0x02,0,0x60,0,0x12,0x12,0x11,0x11,0xd4,0x6e};
    uint8_t null_reply[] = {0x6e,0x80,0xbe,0,0xe6,0xd2,0xd0,0xa4,0x0a,0xf9,0xab,0x2f};
    assert(ds_validate_reply(lg,12,0x60,1) == DS_REPLY_OK);
    assert(lg[1] == 0x51);
    assert(ds_validate_reply(lg,12,0x60,0) == DS_REPLY_INVALID);
    assert(ds_validate_reply(brightness,12,0x10,1) == DS_REPLY_OK);
    assert(ds_validate_reply(brightness,12,0x60,1) == DS_REPLY_INVALID);
    assert(ds_validate_reply(aw,12,0x60,0) == DS_REPLY_OK);
    assert(ds_validate_reply(null_reply,12,0x60,1) == DS_REPLY_NULL);
    assert(ds_validate_reply(lg,10,0x60,1) == DS_REPLY_INVALID);
    lg[9] ^= 1;
    assert(ds_validate_reply(lg,12,0x60,1) == DS_REPLY_INVALID);
    lg[9] ^= 1;
    lg[1] = 0x52;
    assert(ds_validate_reply(lg,12,0x60,1) == DS_REPLY_INVALID);
    lg[1] = 0x51;
    lg[3] = 1; lg[10] ^= 1;
    assert(ds_validate_reply(lg,12,0x60,1) == DS_REPLY_UNSUPPORTED);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory) / 'reply.c'
            exe = Path(directory) / 'reply'
            src.write_text(source)
            include = Path(__file__).resolve().parents[1] / 'tools'
            subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                            '-I', str(include), str(src), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)
