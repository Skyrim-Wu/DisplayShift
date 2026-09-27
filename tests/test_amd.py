import ctypes as c
import sys
import unittest
from unittest.mock import Mock, patch

from shiftcore.amd import AmdAdl, AdapterInfo, DisplayInfo, Route, lg_packet, match_route


class AmdTests(unittest.TestCase):
    def test_ddc_packet_includes_destination_source_and_checksum(self):
        self.assertEqual(bytes.fromhex('6e 50 84 03 f4 00 d1 9c'), lg_packet(0xd1))
        self.assertEqual(bytes.fromhex('6e 50 84 03 f4 00 d0 9d'), lg_packet(0xd0))
        for value in (0, -1, 256, '209'):
            with self.assertRaises(ValueError):
                lg_packet(value)

    def test_windows_abi_layout(self):
        self.assertEqual(1572, c.sizeof(AdapterInfo))
        self.assertEqual(552, c.sizeof(DisplayInfo))

    def test_identity_survives_reorder_and_ignores_names(self):
        routes = [Route(2, 12, 'display3', 'LG'), Route(1, 4, 'display2', 'LG')]
        identities = {'display2': ['lg-id'], 'display3': ['other-lg-id']}
        self.assertEqual(routes[1], match_route(routes, 'LG-ID', identities.__getitem__))

    def test_ambiguous_missing_and_clone_routes_never_guess(self):
        route = Route(1, 4, 'display2', 'LG')
        cases = [([], ['id']), ([route], []), ([route], ['different']),
                 ([route], ['id', 'clone']),
                 ([route, Route(1, 8, 'DISPLAY2', 'LG')], ['id'])]
        for routes, identifiers in cases:
            with self.subTest(routes=routes, identifiers=identifiers):
                with self.assertRaises(RuntimeError):
                    match_route(routes, 'id', lambda _: identifiers)

    def test_native_write_is_send_only_and_propagates_failure(self):
        adl = AmdAdl.__new__(AmdAdl)
        adl.context, adl.dll = c.c_void_p(123), Mock()
        observed = []

        def native(context, adapter, display, options, command, length, data, receive, reply):
            observed.append((adapter, display, options, command, c.string_at(data, length),
                             receive._obj.value, reply))
            return -1

        adl.dll.ADL2_Display_DDCBlockAccess_Get.side_effect = native
        with self.assertRaisesRegex(RuntimeError, '-1'):
            adl.write(Route(1, 4, 'display2', 'LG'), 0xd1)
        self.assertEqual([(1, 4, 0, 0, lg_packet(0xd1), 0, None)], observed)

    def test_close_destroys_context_only_once(self):
        adl = AmdAdl.__new__(AmdAdl)
        adl.context, adl.dll = c.c_void_p(123), Mock()
        adl.close()
        adl.close()
        adl.dll.ADL2_Main_Control_Destroy.assert_called_once()

    @patch('shiftcore.amd.time.sleep')
    def test_lg_repeats_same_packet_with_spacing(self, sleep):
        adl = AmdAdl.__new__(AmdAdl)
        adl.context, adl.dll = c.c_void_p(123), Mock()
        packets = []

        def native(*args):
            packets.append(c.string_at(args[6], args[5]))
            return 0

        adl.dll.ADL2_Display_DDCBlockAccess_Get.side_effect = native
        adl.write(Route(1, 4, 'display2', 'LG'), 0xd1)
        self.assertEqual([lg_packet(0xd1), lg_packet(0xd1)], packets)
        self.assertEqual([(.05,), (.05,)], [call.args for call in sleep.call_args_list])

    @patch('shiftcore.amd.time.sleep')
    def test_disconnect_after_accepted_first_write_is_still_sent(self, sleep):
        adl = AmdAdl.__new__(AmdAdl)
        adl.context, adl.dll = c.c_void_p(123), Mock()
        adl.dll.ADL2_Display_DDCBlockAccess_Get.side_effect = [0, -1]
        adl.write(Route(1, 4, 'display2', 'LG'), 0xd1)
        self.assertEqual(2, adl.dll.ADL2_Display_DDCBlockAccess_Get.call_count)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows backend')
    def test_lg_uses_adl_and_standard_uses_dxva2(self):
        from shiftcore.windows import WindowsBackend
        from shiftcore.engine import Display
        backend = WindowsBackend.__new__(WindowsBackend)
        backend.adl, backend.dx = Mock(), Mock()
        route = Route(1, 4, 'display2', 'LG ULTRAFINE')
        identifier = '\\\\?\\DISPLAY#GSM5BC2#test'
        backend.adl.routes.return_value = [route]
        backend.identifiers_for_gdi = Mock(return_value=[identifier])
        backend.write(Display(identifier, 'LG', handle=55), 0xd1, 'lg-alt')
        backend.adl.write.assert_called_once_with(route, 0xd1)
        backend.dx.SetVCPFeature.assert_not_called()
        backend.write(Display(identifier, 'LG', handle=55), 0x0f, 'standard')
        backend.dx.SetVCPFeature.assert_called_once_with(55, 0x60, 0x0f)
        with self.assertRaisesRegex(RuntimeError, 'LG'):
            backend.write(Display('alienware', 'AW2725QF'), 0xd1, 'lg-alt')
        self.assertEqual(1, backend.adl.write.call_count)


if __name__ == '__main__':
    unittest.main()
