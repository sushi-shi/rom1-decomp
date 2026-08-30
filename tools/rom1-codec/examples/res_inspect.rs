use std::{env, fs, process};

use rom1_codec::resource_archive::{Lookup, ResourceArchive};

fn usage() -> ! {
    eprintln!("usage: cargo run -p rom1-codec --example res_inspect -- <archive.res> [root\\path]");
    process::exit(2);
}

fn main() {
    let mut args = env::args_os();
    let _program = args.next();
    let archive_path = args.next().unwrap_or_else(|| usage());
    let lookup_path = args.next();
    if args.next().is_some() {
        usage();
    }

    let bytes = fs::read(&archive_path).unwrap_or_else(|error| {
        eprintln!("{}: {error}", archive_path.to_string_lossy());
        process::exit(1);
    });
    let archive = ResourceArchive::parse(&bytes).unwrap_or_else(|error| {
        eprintln!("{}: {error}", archive_path.to_string_lossy());
        process::exit(1);
    });
    println!(
        "{}: {} bytes, index 0x{:x}, {} records, root value={} children={} flags=0x{:08x}",
        archive_path.to_string_lossy(),
        bytes.len(),
        archive.index_offset(),
        archive.record_count(),
        archive.root().value(),
        archive.root().child_count(),
        archive.root().flags(),
    );
    for index in 0..archive.record_count() {
        let record = archive.record(index).unwrap();
        println!(
            "{index:6} value=0x{:08x} count/size=0x{:08x} flags=0x{:08x} {:?}",
            record.value(),
            record.child_count_or_size(),
            record.flags(),
            String::from_utf8_lossy(record.name()),
        );
    }

    if let Some(path) = lookup_path {
        let path = path.to_string_lossy();
        let root_end = path
            .as_bytes()
            .iter()
            .position(|&byte| byte == b'\\' || byte == b'/')
            .unwrap_or(path.len());
        match archive.lookup(&path.as_bytes()[..root_end], path.as_bytes()) {
            Ok(Lookup::Missing) => println!("lookup {path:?}: missing"),
            Ok(Lookup::Disabled) => println!("lookup {path:?}: disabled by update.lst"),
            Ok(Lookup::Found(resource)) => println!(
                "lookup {path:?}: offset=0x{:x}, size=0x{:x}, flags=0x{:08x}",
                resource.offset(),
                resource.bytes().len(),
                resource.flags(),
            ),
            Err(error) => {
                eprintln!("lookup {path:?}: {error}");
                process::exit(1);
            }
        }
    }
}
