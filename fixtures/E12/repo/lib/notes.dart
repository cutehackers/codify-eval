import 'package:flutter/foundation.dart';

class Note {
  final int id;
  final String title;
  Note(this.id, this.title);
}

class NoteController extends ChangeNotifier {
  final List<Note> notes = [];
  int nextId = 1;
  void save(String title, {int? id}) {}
}
