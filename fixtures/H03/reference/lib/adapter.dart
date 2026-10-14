import 'dart:convert';

abstract class StatusTransport {
  Future<String> request();
}

class SampleTransport implements StatusTransport {
  @override
  Future<String> request() async => ' {"status":"정상"} ';
}

class StatusAdapter {
  final StatusTransport transport;
  StatusAdapter(this.transport);
  Future<String> fetch() async {
    final data = jsonDecode(await transport.request());
    if (data is! Map ||
        data['status'] is! String ||
        (data['status'] as String).trim().isEmpty)
      throw const FormatException('invalid status');
    return data['status'] as String;
  }
}
