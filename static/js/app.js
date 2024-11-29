// ----------------SLIDESHOW
let slideIndex = 1;
showSlides(slideIndex);

function plusSlides(n) {
  showSlides(slideIndex += n);
}

function currentSlide(n) {
  showSlides(slideIndex = n);
}

function showSlides(n) {
    let slides = document.getElementsByClassName("slide");
  
    if (n > slides.length) {
      slideIndex = 1;
    } else if (n < 1) {
      slideIndex = slides.length;
    }
  
    // Remove 'active' class from all slides
    for (let i = 0; i < slides.length; i++) {
      slides[i].classList.remove('active');
    }
  
    // Add 'active' class to the current slide
    slides[slideIndex - 1].classList.add('active');
  
    // Handle transition from last slide to first
    if (n === slides.length && slideIndex === 1) {
      slides[slideIndex - 1].style.transition = 'opacity 0s ease-in-out';
      setTimeout(() => {
        slides[slideIndex - 1].style.transition = 'opacity 1s ease-in-out';
      }, 10);
    }
  
    // Automatically transition to the next slide every 30 seconds
    setTimeout(() => {
      showSlides(slideIndex += 1);
    }, 30000);
  }