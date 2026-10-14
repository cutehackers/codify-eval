import 'package:flutter/material.dart';

void main() => runApp(ShelfApp(controller: ShelfController()));

class Book {
  final String isbn;
  final String title;
  const Book(this.isbn, this.title);
}

class ShelfController extends ChangeNotifier {
  final List<Book> books = [];
  void add(Book book) {
    final index = books.indexWhere((b) => b.isbn == book.isbn);
    if (index < 0) {
      books.add(book);
    } else {
      books[index] = book;
    }
    notifyListeners();
  }
}

class ShelfApp extends StatefulWidget {
  final ShelfController controller;
  const ShelfApp({super.key, required this.controller});
  @override
  State<ShelfApp> createState() => _ShelfAppState();
}

class _ShelfAppState extends State<ShelfApp> {
  final isbn = TextEditingController();
  final title = TextEditingController();
  @override
  void dispose() {
    isbn.dispose();
    title.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
      home: Scaffold(
          body: AnimatedBuilder(
              animation: widget.controller,
              builder: (_, _) => Column(children: [
                    TextField(key: const Key('isbn'), controller: isbn),
                    TextField(key: const Key('title'), controller: title),
                    TextButton(
                        key: const Key('add'),
                        onPressed: () =>
                            widget.controller.add(Book(isbn.text, title.text)),
                        child: const Text('등록')),
                    for (final b in widget.controller.books)
                      Text('${b.isbn}: ${b.title}')
                  ]))));
}
