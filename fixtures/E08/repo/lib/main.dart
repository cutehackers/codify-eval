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
    final result = await widget.adapter.load();
    if (mounted) setState(() => news = result);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
          body: Column(children: [
        if (busy) const Text('불러오는 중'),
        if (error != null) Text(error!),
        for (final title in news) Text(title),
        TextButton(
            key: const Key('retry'),
            onPressed: load,
            child: const Text('다시 시도')),
      ]));
}
