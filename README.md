# Website Replicator

This project exists merely as a proof of concept.
There are obvious design flaws in the way that POST requests are altered and other endpoints related to the website.
However authentication of reformatted POST requests and other entities was out of the scope of the content of this project.

This project does not attempt to replace every single URL with one of the main site, but it does attempt to mostly keep the user "trapped" at the destination website using relative paths.
This project will download images and host them locally, it will reformat POST requests on forms, and it will replace all requests to CSS and images with necessary data.

This acts as a somewhat man-in-the-middle attack by replicating a site. Instead of being a traditional man in the middle, this is more of a proxy that can be deployed in a sort of phishing attack. Due to the nature of the web, replicating any site can be extremely difficult, especially those with Javascript.

Due to this being a proof of concept, it doesn't attempt to match any site 1:1, but it will replicate, in some respect, many sites semi-closely as long as they don't use Javascript to gate content (like Instagram). This will also print out destination links (by the nature of Bottle request print-outs), prints out resource downloads (CSS and images), and it will print out all form data that is sent with a POST request.
