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
    final data = jsonDecode(await transport.request()) as Map<String, dynamic>;
    return data['status'] as String;
  }
}
