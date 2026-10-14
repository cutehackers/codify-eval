import 'package:flutter/material.dart';
import 'adapter.dart';
export 'adapter.dart';

void main() => runApp(
    MaterialApp(home: StatusPage(adapter: StatusAdapter(SampleTransport()))));

class StatusPage extends StatefulWidget {
  final StatusAdapter adapter;
  const StatusPage({super.key, required this.adapter});
  @override
  State<StatusPage> createState() => _StatusPageState();
}

class _StatusPageState extends State<StatusPage> {
  String status = '';
  bool busy = false;
  @override
  void initState() {
    super.initState();
    refresh();
  }

  Future<void> refresh() async {
    if (busy) return;
    setState(() {
      busy = true;
      status = '확인 중';
    });
    try {
      final value = await widget.adapter.fetch();
      if (mounted) setState(() => status = value);
    } catch (_) {
      if (mounted) setState(() => status = '상태 확인 실패');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
          body: Column(children: [
        Text(status),
        TextButton(
            key: const Key('refresh'),
            onPressed: busy ? null : refresh,
            child: const Text('새로고침'))
      ]));
}
