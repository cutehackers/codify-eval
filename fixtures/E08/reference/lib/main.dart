import 'package:flutter/material.dart';
import 'service.dart';
export 'service.dart';

void main() =>
    runApp(MaterialApp(home: NewsPage(adapter: NewsAdapter(SampleService()))));

class NewsPage extends StatefulWidget {
  final NewsAdapter adapter;
  const NewsPage({super.key, required this.adapter});
  @override
  State<NewsPage> createState() => _NewsPageState();
}

class _NewsPageState extends State<NewsPage> {
  List<String> news = [];
  bool busy = false;
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    if (busy) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = await widget.adapter.load();
      if (mounted) setState(() => news = result);
    } catch (_) {
      if (mounted) setState(() => error = '소식을 불러오지 못했습니다');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
          body: Column(children: [
        if (busy) const Text('불러오는 중'),
        if (error != null) Text(error!),
        if (!busy && error == null && news.isEmpty) const Text('소식 없음'),
        for (final title in news) Text(title),
        TextButton(
            key: const Key('retry'),
            onPressed: busy ? null : load,
            child: const Text('다시 시도')),
      ]));
}
