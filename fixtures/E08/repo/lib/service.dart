abstract class RemoteService {
  Future<List<String>> fetch();
}

class SampleService implements RemoteService {
  @override
  Future<List<String>> fetch() async => ['소식'];
}

class NewsAdapter {
  final RemoteService service;
  NewsAdapter(this.service);
  Future<List<String>> load() => service.fetch();
}
